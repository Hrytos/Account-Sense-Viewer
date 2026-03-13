"""
AI Summarizer Service
Consolidated AI logic for generating account, company, and assertion summaries.
"""

from src.core.clients import get_openai_client

def generate_account_summary(data):
    """
    Generate an AI-powered summary of the account data.
    """
    try:
        client = get_openai_client()
        
        company_name = data['company_name']
        site_size = data['site_size']
        location = data['location']
        events = data['events']
        assertions = data['assertions']
        
        prompt = f"""You are an expert business analyst. Analyze the following company data and provide a concise, insightful summary.

Company: {company_name}
Location: {location.get('full_address', 'Not available')}
Site Size: {f"{site_size:,.0f} sq ft" if site_size else "Not available"}

FINANCIAL DATA:
"""
        if events['finance']:
            for event in events['finance']:
                value = event['event_type_value'] or 'Not Found'
                verified = '✓' if event['verified'] else '✗'
                prompt += f"- {event['event_type']}: {value} (Verified: {verified})\n"
        else:
            prompt += "- No financial data available\n"
        
        prompt += "\nBUSINESS ACTIVITIES:\n"
        if events['business']:
            for event in events['business']:
                value = event['event_type_value'] or 'No Information Found'
                prompt += f"- {event['event_type']}: {value}\n"
        else:
            prompt += "- No business activity data available\n"
        
        prompt += "\nOPERATIONAL DETAILS:\n"
        if events['operational']:
            for event in events['operational'][:10]:
                value = event['event_type_value'] or 'Not available'
                prompt += f"- {event['event_type']}: {value}\n"
        else:
            prompt += "- No operational data available\n"
        
        prompt += "\nCUSTOMER INFORMATION:\n"
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
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert business analyst specializing in warehouse and logistics operations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def generate_company_overview(company_name, full_address):
    """
    Generate a factual overview of the company based on name and location.
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

Be factual and professional."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a business research assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating company overview: {str(e)}"

def generate_assertion_summary(assertions):
    """
    Generate a narrative summary of assertions.
    """
    try:
        client = get_openai_client()
        if not assertions:
            return "No assertions available to analyze."
        
        prompt = f"Analyze the following {len(assertions)} assertions about a company and provide a narrative summary.\n\nASSERTIONS DATA:\n"
        for i, assertion in enumerate(assertions, 1):
            supporting = f"{assertion['supporting_score']:.2f}" if assertion['supporting_score'] is not None else 'N/A'
            opposing = f"{assertion['opposing_score']:.2f}" if assertion['opposing_score'] is not None else 'N/A'
            net = f"{assertion['net_score']:.2f}" if assertion['net_score'] is not None else 'N/A'
            classification = assertion['classification'] or 'UNKNOWN'
            prompt += f"{i}. [{assertion['assertion_type']}] {assertion['assertion_text']} (Support: {supporting}, Oppose: {opposing}, Net: {net}, Class: {classification})\n"
        
        prompt += "\nProvide a concise narrative summary (5-7 sentences) covering key insights, patterns, and the overall picture."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a data analyst specializing in evidence-based assessment."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating assertion summary: {str(e)}"
