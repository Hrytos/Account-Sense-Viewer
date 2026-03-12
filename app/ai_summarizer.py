"""
AI Summarizer Module
Uses GPT-4o mini to generate intelligent summaries of account data.
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


def generate_account_summary(data):
    """
    Generate an AI-powered summary of the account data using GPT-4o mini.
    
    Args:
        data (dict): Dictionary containing all account data including:
            - company_name
            - site_size
            - location
            - events (finance, business, operational, customer)
            - assertions
    
    Returns:
        str: AI-generated summary of the account
    """
    try:
        client = get_openai_client()
        
        # Prepare the data for the prompt
        company_name = data['company_name']
        site_size = data['site_size']
        location = data['location']
        events = data['events']
        assertions = data['assertions']
        
        # Build a comprehensive prompt with all the data
        prompt = f"""You are an expert business analyst. Analyze the following company data and provide a concise, insightful summary.

Company: {company_name}
Location: {location.get('full_address', 'Not available')}
Site Size: {f"{site_size:,.0f} sq ft" if site_size else "Not available"}

FINANCIAL DATA:
"""
        
        # Add financial events
        if events['finance']:
            for event in events['finance']:
                value = event['event_type_value'] or 'Not Found'
                verified = '✓' if event['verified'] else '✗'
                prompt += f"- {event['event_type']}: {value} (Verified: {verified})\n"
        else:
            prompt += "- No financial data available\n"
        
        prompt += "\nBUSINESS ACTIVITIES:\n"
        
        # Add business events
        if events['business']:
            for event in events['business']:
                value = event['event_type_value'] or 'No Information Found'
                prompt += f"- {event['event_type']}: {value}\n"
        else:
            prompt += "- No business activity data available\n"
        
        prompt += "\nOPERATIONAL DETAILS:\n"
        
        # Add key operational events (limit to top 10)
        if events['operational']:
            for event in events['operational'][:10]:
                value = event['event_type_value'] or 'Not available'
                prompt += f"- {event['event_type']}: {value}\n"
            if len(events['operational']) > 10:
                prompt += f"- ... and {len(events['operational']) - 10} more operational details\n"
        else:
            prompt += "- No operational data available\n"
        
        prompt += "\nCUSTOMER INFORMATION:\n"
        
        # Add customer events
        if events['customer']:
            for event in events['customer']:
                if event['metadata'] and 'is_3pl' in event['metadata']:
                    is_3pl = event['metadata']['is_3pl']
                    prompt += f"- 3PL Status: {'Yes' if is_3pl else 'No'}\n"
                if event['event_type_value']:
                    prompt += f"- {event['event_type']}: {event['event_type_value']}\n"
        else:
            prompt += "- No customer data available\n"
        
        prompt += f"\nASSERTIONS: {len(assertions)} assertions evaluated\n"
        
        # Add assertion summary
        if assertions:
            supported = len([a for a in assertions if a['classification'] and 'SUPPORTED' in a['classification']])
            contested = len([a for a in assertions if a['classification'] and 'CONTESTED' in a['classification']])
            opposed = len([a for a in assertions if a['classification'] and 'OPPOSED' in a['classification']])
            prompt += f"- Supported: {supported}, Contested: {contested}, Opposed: {opposed}\n"
        
        prompt += """

Please provide a concise 5-6 sentence summary that covers:
1. Brief overview of the company and its operations
2. Key financial and business highlights
3. Notable operational capabilities
4. Overall assessment and insights

Be professional, direct, and focus on the most important actionable insights."""
        
        # Call GPT-4o mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert business analyst specializing in warehouse and logistics operations. Provide clear, insightful summaries based on data."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"


def generate_quick_summary(data):
    """
    Generate a quick 2-3 sentence summary of the account.
    
    Args:
        data (dict): Dictionary containing account data
    
    Returns:
        str: Brief AI-generated summary
    """
    try:
        client = get_openai_client()
        
        company_name = data['company_name']
        site_size = data['site_size']
        location = data['location']
        
        prompt = f"""Provide a 2-3 sentence executive summary for:

Company: {company_name}
Location: {location.get('full_address', 'Not available')}
Site Size: {f"{site_size:,.0f} sq ft" if site_size else "Not available"}

Be concise and professional."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a business analyst. Provide brief, professional summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error: {str(e)}"
