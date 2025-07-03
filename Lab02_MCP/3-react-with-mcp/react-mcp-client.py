import asyncio, json, os
from typing import Dict, Any, List, Iterable

from openai import AsyncOpenAI, AzureOpenAI          # ← keep Azure creds for chat
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from prompts import react_prompt_template
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv

load_dotenv()
# Azure OpenAI Configuration
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_API_VERSION = os.getenv("AZURE_AI_API_VERSION", "2024-12-01-preview")
CREDENTIAL = DefaultAzureCredential()
TOKEN_PROVIDER = get_bearer_token_provider(CREDENTIAL, "https://cognitiveservices.azure.com/.default")


class ReActAgent:
    def __init__(self, server_script: str = "mcp_server.py") -> None:
        self.react_prompt = react_prompt_template
        self._server_script = server_script
        self._exit_stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None
        self.tools_description: str = ""  

    # formats the thought process history as a string for prompt context
    def _format_thought_history(self, thought_process: List[Dict[str, Any]]) -> str:
        history = ""
        for step in thought_process:
            history += f"Thought: {step['thought']}\n"
            if step.get("action"):
                history += f"Action: {json.dumps(step['action'])}\n"
            if step.get("observation"):
                history += f"Observation: {step['observation']}\n"
            if step.get("pause_reflection"):
                history += f"PAUSE: {step['pause_reflection']}\n"
        return history
    
    # connect to the mcp server
    async def _connect(self) -> None:
        """Spin up / attach to the MCP server exactly once."""
        if self.session:                            
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(
                StdioServerParameters(command="python", args=[self._server_script])
            )
        )
        stdio, write = stdio_transport
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )
        await self.session.initialize()

        # Build description string for prompt
        tools = await self.session.list_tools()
        self.tools_description = "\n".join(
            f"{t.name}: \"{t.description}\"" for t in tools.tools
        )
    # send a request to OpenAI and get the response
    async def _get_openai_response(self, prompt: str, query: str) -> str:

        oai_client = AzureOpenAI(
            azure_endpoint=AZURE_AI_ENDPOINT,
            api_version=AZURE_AI_API_VERSION,
            azure_ad_token_provider=TOKEN_PROVIDER,
            )
    
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query}
        ]

        try:
            response = oai_client.chat.completions.create(
                        model = "gpt-4o",
                        messages = messages,
                        temperature=0.7,
                        max_tokens=1000
            )
            print(f"\nAgent response: {response.choices[0].message.content}")
            return  response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {e}"
        
    # executes the ReAct loop      
    async def run(self, query: str) -> str:
        thought_process: List[Dict[str, Any]] = []

        while True:
            # Prepare prompt and appends thought history if available
            prompt = (
                self.react_prompt.format(tool_descriptions=self.tools_description)
            )
            if thought_process:
                prompt += self.format_thought_history(thought_process)

            # Get next step from LLM (assumes JSON-formatted output)
            step_text = await self._get_openai_response(prompt, query)

            try:
                step = json.loads(step_text)
            except json.JSONDecodeError as e:
                return f"Could not parse LLM JSON: {e}\nRaw: {step_text}"

            # When final answer is present, return it
            if "final_answer" in step:
                # (Optional) print the full chain of thought
                print(self._format_thought_history(thought_process))
                return step["final_answer"]

            # Continues reasoning 
            thought = step.get("thought", "")
            actions = step.get("action", []) 
            pause   = step.get("pause", None)

            if not isinstance(actions, list):
                actions = [actions]  

            # Execute each tool call
            for act in actions:
                tool_name  = act.get("tool_choice")
                tool_input = act.get("tool_input")

                if not tool_name or tool_input is None:
                    thought_process.append(
                        {
                            "thought": thought,
                            "action": act,
                            "observation": "Missing tool_choice/tool_input",
                            "pause": pause,
                        }
                    )
                    continue

                tool_func = getattr(self.tools, tool_name, None)
                if callable(tool_func):
                    try:
                        result = tool_func(tool_input)
                    except Exception as ex:
                        result = f"Tool runtime error: {ex}"
                else:
                    result = f"Unknown tool '{tool_name}'"

                thought_process.append(
                    {
                        "thought": thought,
                        "action": act,
                        "observation": result,
                        "pause": pause,
                    }
                )
    async def aclose(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()

async def main() -> None:
    agent = ReActAgent()  
    try:
        q = input("Enter your query: ")
        answer = await agent.run(q)
        print("\nFinal Answer:", answer)
    finally:
        await agent.aclose()

if __name__ == "__main__":
    asyncio.run(main())