import asyncio
import requests
import json
import os
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from prompts import react_prompt_template
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
    
     # formats the thought process history as a string for prompt context
    def _format_thought_history(self, thought_process: List[Dict[str, Any]]) -> str:
        """
        Formats the thought process history as a string for prompt context.
        """
        history = ""
        for step in thought_process:
            history += json.dumps(step, ensure_ascii=False) + "\n"
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

     # executes the ReAct loop   
    async def run(self, query: str) -> str:
        thought_process: List[Dict[str, Any]] = []

        while True:
            # Prepare prompt and appends thought history if available
            prompt = (
                self.react_prompt + "\n"
            )
            if thought_process:
                prompt += self._format_thought_history(thought_process)

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
           
            thought_process.append(step)
            
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