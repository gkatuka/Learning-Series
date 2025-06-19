import asyncio
import requests
import json
import os
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from prompts import react_prompt_template
from tools import Tools
from toolbox import ToolBox
from collections.abc import Iterable
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()
# Azure OpenAI Configuration
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_API_VERSION = os.getenv("AZURE_AI_API_VERSION", "2024-12-01-preview")
CREDENTIAL = DefaultAzureCredential()
TOKEN_PROVIDER = get_bearer_token_provider(CREDENTIAL, "https://cognitiveservices.azure.com/.default")


class ReActAgent:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_AI_ENDPOINT,
            api_version=AZURE_AI_API_VERSION,
            azure_ad_token_provider=TOKEN_PROVIDER,
        )
        self.react_prompt = react_prompt_template
        self.tools = Tools()
        self.tools_description = self._prepare_tools()  
    
    @staticmethod
    def _flatten(items: Iterable) -> Iterable:
        """Recursively flatten nested iterables (helper for _prepare_tools)."""
        for obj in items:
            if isinstance(obj, (list, tuple, set)):
                yield from ReActAgent._flatten(obj)
            else:
                yield obj

    def _prepare_tools(self) -> str:
        """
        Collect all public callables from Tools.user_functions (or the class itself)
        and return a nicely formatted description for the prompt.
        """
        toolbox = ToolBox()

        # If the Tools class exposes an explicit set, prefer that
        candidates = (
            self.tools.user_functions
            if hasattr(self.tools, "user_functions")
            else [
                v
                for k, v in self.tools.__dict__.items()
                if callable(v) and not k.startswith("_")
            ]
        )

        toolbox.store(self._flatten(candidates))
        return toolbox.describe_tools()

    # formats the thought process history as a string for prompt context        
    def _format_thought_history(self, thought_process: List[Dict[str, Any]]) -> str:
        """
        Formats the thought process history as a string for prompt context.
        """
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
    
    # send a request to OpenAI and get the response
    async def _get_openai_response(self, prompt: str, query: str) -> str:
    
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query}
        ]

        try:
            response = self.client.chat.completions.create(
                        model = "gpt-4o",
                        messages = messages,
                        temperature=0.1,
                        max_tokens=1000
            )
            print(f"\nAgent response: {response.choices[0].message.content}")
            return  response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {e}"
        
    async def run(self, query: str) -> str:
        # executes the ReAct loop 
        thought_process: List[Dict[str, Any]] = []

        while True:
            # Prepare prompt and appends thought history if available
            prompt = (
                self.react_prompt.format(tool_descriptions=self.tools_description)
            )
            if thought_process:
                prompt += self.format_thought_history(thought_process)

            # Get next step from LLM 
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
                actions = [actions]  # allow single-dict fall-back

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
            
async def main():
    try:
        agent = ReActAgent()
        
        query = input("Enter your Query : ")
        response = await agent.run(query)
        print("\nFinal Answer:", response)
    
    except Exception as e:
        print(f"Error running agent: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 