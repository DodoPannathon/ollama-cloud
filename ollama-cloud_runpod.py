"""
Ollama Cloud AI Client - OpenAI Compatible Mode
Interactive model selector with async HTTP requests and spinner
Uses OpenAI /v1/chat/completions API format
"""

import json
import aiohttp
import asyncio
import inquirer
from pathlib import Path
import ast
from typing import Tuple
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
URL = os.getenv("URLS")
API_KEY = os.getenv("API_KEY")
BASE_PATH = Path(__file__).resolve().parent
CONVERSATION_PATH = BASE_PATH / "conversations"

if not CONVERSATION_PATH.exists():
    print("Creating conversations directory...")
    CONVERSATION_PATH.mkdir()

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def status_display(status: str,num: int):
    """Return a user-friendly status message."""
    status_mapping = {
        "IN_PROGRESS": "in progress",
        "IN_QUEUE": "in queue",
    }
    if num % 2 == 0:
        print(f"\r\033[90m{status_mapping.get(status, status)}...\033[0m", end="", flush=True)
    else:
        print(f"\r\033[90m{status_mapping.get(status, status)}   \033[0m", end="", flush=True)

def convert_title_file(title: str) -> str:
    return f"{title.replace(' ','_')}.txt"

def continue_command(title: str) -> list:
    with open(CONVERSATION_PATH / title, 'r', encoding='utf-8') as file:
        print("=" * 50)
        context = []
        lines = file.readlines()
        for line in lines:
            line_object = ast.literal_eval(line[:-1])
            context.append(line_object)
            if line_object["role"] == "user":
                print(f"> {line_object["content"]}")
            elif line_object["role"] == "assistant":
                print(line_object["content"])
            print("=" * 50)
        return context
    

async def prompt_input(context,session_name) -> tuple[list,str,str]:
    """Prompt user for input asynchronously."""

    prompt = await asyncio.get_event_loop().run_in_executor(
        None, lambda: input("> ")
    )

    if prompt[:9] == "/continue":
        if prompt[10:]:
            session_name = convert_title_file(prompt[10:])
            context = continue_command(convert_title_file(prompt[10:]))
            return context,"",session_name

        session_list = [item.name for item in Path(CONVERSATION_PATH).iterdir()]
        if not session_list:
            print("No previous conversation")
            return context,"",session_name

        question = [
            inquirer.List(
                'conversation',
                message="Select a previous conversation",
                choices=session_list,
            )
        ]

        answer = inquirer.prompt(question)

        if answer:
            session_name = answer["conversation"]
            context = continue_command(answer["conversation"])
            return context,"",session_name

        print("No selected conversation")
        return context,"",session_name
    elif prompt[:5] == "/save":
        if session_name:
            with open(CONVERSATION_PATH / session_name, 'w', encoding='utf-8') as file:
                for line in context:
                    file.write(f'{line}\n')
        elif prompt[6:]:
            session_name = convert_title_file(prompt[6:])
            with open(CONVERSATION_PATH / convert_title_file(prompt[6:]), 'w', encoding='utf-8') as file:
                for line in context:
                    file.write(f'{line}\n')
        return context,"",session_name
    elif prompt[:5] == "/exit":
        if session_name:
            with open(CONVERSATION_PATH / session_name, 'w', encoding='utf-8') as file:
                for line in context:
                    file.write(f'{line}\n')
        elif prompt[6:]:
            with open(CONVERSATION_PATH / convert_title_file(prompt[6:]), 'w', encoding='utf-8') as file:
                for line in context:
                    file.write(f'{line}\n')
        print("\nExit ollama cloud")
        return context,"/exit",session_name
    else:
        context.append({"role":"user","content":prompt})
        return context,prompt,session_name

async def fetch_data(url: str, model: str, context) -> str:
    """
    Send prompts to the Ollama API and display responses.
    
    Args:
        url: Base URL of the Ollama API
        model: Selected model name
    """

    full_response = ""
    stream_reasoning = True
    job_id = ""

    payload = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": model,
                "messages": context,
                "stream": True
            }
        }
    }

    async with aiohttp.ClientSession() as session:
        
        try:
            async with session.post(f"{url}/run", json=payload, headers=headers) as response:
                if response.status == 200:
                    job_id = (await response.json())["id"]
                else:
                    print(f"\nFailed to submit job: {response.status}")
                    spinner_task_handle.cancel()
                    try:
                        await spinner_task_handle
                    except asyncio.CancelledError:
                        pass
                    return ""
            n = 0
            while True:
                async with session.get(f"{url}/stream/{job_id}", headers=headers) as response:
                    if response.status == 200:
                        n += 1
                        data = await response.json()
                        status = data.get("status", "")
                        stream = data.get("stream", [])

                        if status in ("COMPLETED", "FAILED", "CANCELLED"):break
                        if not stream:
                            status_display(status,n)
                        else:
                            if n > 0:
                                print("\r" + " " * 50 + "\r", end="", flush=True)
                            n = -1
                            for item in stream:
                                raw = item.get("output", "")
                                if raw == "data: [DONE]":
                                    print()
                                    break
                                data = json.loads(raw[6:-2].strip())
                                delta = data["choices"][0]["delta"]
                                reasoning = delta.get("reasoning", "")
                                content = delta.get("content", "")
                                if reasoning:
                                    print(f"\033[90m{reasoning}\033[0m", end="", flush=True)
                                else:
                                    if stream_reasoning:
                                        print()
                                    stream_reasoning = False
                                if content:
                                    full_response += content
                                    print(content, end="", flush=True)
                    else:
                        print(f"\nFailed to fetch data: {response.status}")
        except aiohttp.ClientError as e:
            print(f"\nNetwork error: {e}")
        except json.JSONDecodeError as e:
            print(f"\nFailed to parse response: {e}")
        except KeyError as e:
            print(f"\nUnexpected response format: {e}")

async def main():
    """Main entry point for the Ollama Cloud AI client."""

    session_name = ''
    context = []

    print('=' * 50)
    print("  Ollama Cloud AI Client")
    print('=' * 50)
    
    model = await asyncio.get_event_loop().run_in_executor(
        None, lambda: input("type you model: ")
    )

    print(f"\nConnected to model: {model}")
    print("Type your prompts (/exit to exit)\n")

    while True:
        print('=' * 50)

        context,prompt,session_name = await prompt_input(context,session_name)

        if prompt == "/exit":
            break
        if model and prompt:
            # print("running...")
            full_response = await fetch_data(URL, model, context)
            if full_response:
                context.append({"role":"assistant","content":full_response})
        elif model and not prompt:
            pass
        else:
            print("Failed to initialize. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExit ollama cloud")