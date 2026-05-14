import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

async def main():
    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash', 
            contents='Hello, reply in JSON {"msg": "hi"}', 
            config=GenerateContentConfig(temperature=0.1)
        )
        print("Success:", response.text)
    except Exception as e:
        print("Exception Type:", type(e).__name__)
        print("Exception Message:", str(e))

asyncio.run(main())
