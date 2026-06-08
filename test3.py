import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
api_key = os.getenv('API_KEY')
base_path = Path(__file__).resolve().parent
conversation_path = base_path / "conversation"

print(conversation_path.exists())
if not conversation_path.exists():
 print("creat new conversation dir")
 Path("conversation").mkdir()

print(api_key)
print(conversation_path)
with open(f"{conversation_path}/test.txt",'r',encoding='utf-8') as file:
 lines = file.readlines()
 print(lines)