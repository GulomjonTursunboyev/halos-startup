import asyncio
import aiohttp
import os

KOTIB_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb21wYW55" # Truncated
# I'll get the full key from the file

async def test_kotib():
    # Use the full key from ai_assistant.py or env if exists
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb21wYW55" + "..." # truncated
    
    # Read the actual key from ai_assistant.py
    with open("app/ai_assistant.py", "r", encoding="utf-8") as f:
        for line in f:
            if "KOTIB_API_KEY =" in line:
                key = line.split("=")[1].strip().strip('"').strip("'")
                break
    
    print(f"Testing KOTIB_API_KEY: {key[:10]}...")
    url = "https://developer.kotib.ai/api/v1/balance"
    headers = {'Authorization': f'Bearer {key}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print(f"Status: {response.status}")
            text = await response.text()
            print(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(test_kotib())
