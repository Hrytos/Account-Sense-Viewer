"""
Assertion Summary Module
Analyzes assertions and generates an AI-powered narrative summary using GPT-4o mini.
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


def generate_assertion_summary(assertions):
    """
    Generate an AI-powered narrative summary of assertions using GPT-4o mini.
    
    Args:
        assertions (list): List of assertion dictionaries with:
            - assertion_text
            - assertion_type
            - supporting_score
            - opposing_score
            - net_score
            - classification
    
    Returns:
        str: AI-generated narrative summary covering:
            - Key insights (what's supported vs opposed)
            - Patterns in the data
            - Overall narrative explaining the picture
    """
    try:
        client = get_openai_client()
        
        if not assertions:
            return "No assertions available to analyze."
        
        # Prepare assertion data for the prompt
        prompt = f"""Analyze the following {len(assertions)} assertions about a company and provide a narrative summary.

ASSERTIONS DATA:
"""
        
        # Add each assertion with its scores and classification
        for i, assertion in enumerate(assertions, 1):
            supporting = f"{assertion['supporting_score']:.2f}" if assertion['supporting_score'] is not None else 'N/A'
            opposing = f"{assertion['opposing_score']:.2f}" if assertion['opposing_score'] is not None else 'N/A'
            net = f"{assertion['net_score']:.2f}" if assertion['net_score'] is not None else 'N/A'
            classification = assertion['classification'] or 'UNKNOWN'
            
            prompt += f"""
{i}. [{assertion['assertion_type']}] {assertion['assertion_text']}
   - Supporting Score: {supporting}
   - Opposing Score: {opposing}
   - Net Score: {net}
   - Classification: {classification}
"""
        
        prompt += """

Provide a concise narrative summary (5-7 sentences) that covers:
1. Key insights about what's supported vs opposed
2. Patterns in the data
3. Overall narrative explaining the picture

Be brief and focus only on the most critical findings. Write in a professional, analytical tone."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a data analyst specializing in evidence-based assessment. Provide brief, insightful summaries in 5-7 sentences maximum."
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
        return f"Error generating assertion summary: {str(e)}"
