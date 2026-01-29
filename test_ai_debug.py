import google.generativeai as genai
import os
import json
import traceback
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

try:
    genai.configure(api_key=api_key)
    # List models to check if API key is valid
    print("Listing models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Found model: {m.name}")
            
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hello, write one word.")
    print(f"AI Response: {response.text}")
except Exception as e:
    print(f"Error type: {type(e)}")
    print(f"Error message: {e}")
    traceback.print_exc()
