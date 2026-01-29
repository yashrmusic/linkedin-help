import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Using API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

sys_instruction = """Extract candidate information from the following text and return it in JSON format.
Fields to extract: name, email, phone, position, start_date, salary, test_date.
If a field is not found, leave it as an empty string. Output ONLY the JSON."""

prompt = "Rahul Gupta, rahul@example.com, Intern, joining 5 Feb 2026, salary 15000"

try:
    response = model.generate_content(f"{sys_instruction}\n\nCandidate Text: {prompt}")
    print("AI Response:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
