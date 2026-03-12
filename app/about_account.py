"""
About Account Module
Generates a general company overview using GPT-4o mini based on company name and address.
"""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv


def get_openai_client():
    """
    Create and return an OpenAI client using API key from .env file.
    """
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY in .env file")
    
    # Use an explicit HTTP client to avoid proxies-argument incompatibilities.
    return OpenAI(api_key=api_key, http_client=httpx.Client())


def generate_company_overview(company_name, full_address):
    """
    Generate a 5-sentence general overview about the company using GPT-4o mini.
    
    Args:
        company_name (str): Name of the company
        full_address (str): Full address of the company location
    
    Returns:
        str: 5-sentence company overview
    """
    try:
        client = get_openai_client()
        
        prompt = f"""Provide a general 5-sentence overview about this company:

Company Name: {company_name}
Location: {full_address}

Include information about:
- What the company does (business description)
- Industry/sector
- Type of operations
- Any notable characteristics

Be factual and professional. If you don't have specific information, provide general context about what companies with this name typically do in this industry."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business research assistant. Provide concise, factual company overviews based on company names and locations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=250
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error generating company overview: {str(e)}"
