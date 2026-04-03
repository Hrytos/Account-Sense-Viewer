"""
AI Summarizer Service
Consolidated AI logic for generating account, company, and assertion summaries.
"""

import json
from typing import Any, Dict, List

from src.core.clients import get_openai_client
from src.services.report_metadata import build_teaser_context_lines


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

def generate_assertion_summary(assertions, company_slug, site_id):
    """
    Generate a narrative summary of SUPPORTED assertions with full evidence.
    Focuses on STRONGLY/SUBSTANTIALLY/PARTIALLY SUPPORTED classifications,
    prioritized by strength, and includes supporting/opposing markdown evidence.
    """
    try:
        from src.services.assertion_from_supabase import fetch_supporting_and_opposing
        
        client = get_openai_client()
        if not assertions:
            return "No assertions available to analyze."
        
        # Filter to supported classifications only
        SUPPORTED_CLASSES = {
            "STRONGLY SUPPORTED": 1,
            "SUBSTANTIALLY SUPPORTED": 2,
            "PARTIALLY SUPPORTED": 3
        }
        
        supported = [
            a for a in assertions
            if (a.get("classification") or "").upper() in SUPPORTED_CLASSES
        ]
        
        if not supported:
            return "No supported assertions to analyze."
        
        # Sort by priority tier (STRONGLY → SUBSTANTIALLY → PARTIALLY), then net_score descending
        supported.sort(key=lambda a: (
            SUPPORTED_CLASSES.get((a.get("classification") or "").upper(), 999),
            -(a.get("net_score") or 0)
        ))
        
        # Fetch markdown evidence for each assertion
        for assertion in supported:
            assertion_id = assertion.get("assertion_id")
            if assertion_id:
                try:
                    md = fetch_supporting_and_opposing(company_slug, site_id, assertion_id)
                    assertion["supporting_md"] = md.get("supporting", "(Evidence not available)")
                    assertion["opposing_md"] = md.get("opposing", "(Evidence not available)")
                except Exception:
                    assertion["supporting_md"] = "(Evidence not available)"
                    assertion["opposing_md"] = "(Evidence not available)"
            else:
                assertion["supporting_md"] = "(No assertion_id - evidence not available)"
                assertion["opposing_md"] = "(No assertion_id - evidence not available)"
        
        # Build enhanced prompt with full evidence
        prompt = """Persona: You are an expert warehouse automation advisor.


Input data description: You are given the following inputs: set of statements about a warehouse, opinion classification for each statement (strongly supported, substantially supported, partially supported, weakly supported, not supported and contested), supporting arguments with evidence and opposing arguments with evidence.


Task: Your job is to determine the following:
Is this warehouse a good candidate for Autonomous Tuggers? Give specific reasons by referencing only the input data. Strictly consider only those statements where opinion classification is strongly supported, substantially supported and partially supported - in that order. 
If yes to the above, what are the top 3 key drivers and top 3 risks for a successful sale of autonomous tugger. Do not give generic answers, refer only to the input data provided. If no, ignore.



SUPPORTED ASSERTIONS (prioritized by classification strength):

"""
        
        for i, assertion in enumerate(supported, 1):
            supporting_score = f"{assertion['supporting_score']:.2f}" if assertion.get('supporting_score') is not None else 'N/A'
            opposing_score = f"{assertion['opposing_score']:.2f}" if assertion.get('opposing_score') is not None else 'N/A'
            net_score = f"{assertion['net_score']:.2f}" if assertion.get('net_score') is not None else 'N/A'
            classification = assertion.get('classification') or 'UNKNOWN'
            assertion_text = assertion.get('assertion_text') or ''
            
            prompt += f"""---
ASSERTION #{i} - {classification}
Statement: {assertion_text}
Scores: Support={supporting_score}, Oppose={opposing_score}, Net={net_score}

SUPPORTING EVIDENCE:
{assertion.get('supporting_md', '(Not available)')}

OPPOSING EVIDENCE:
{assertion.get('opposing_md', '(Not available)')}
---

"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a logic analyst specializing in summarizing and finding patterns in the given information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating assertion summary: {str(e)}"


def generate_operations_teaser_variations(metadata: Dict[str, Any]) -> List[str]:
    """
    Produce 3–5 short, distinct teaser lines for the operations report.
    Hooks attention; does not replace reading the full report.
    """
    lines = build_teaser_context_lines(metadata)
    context = "\n".join(lines).strip()
    if not context:
        raise ValueError("No teaser context available from report metadata.")

    system = (
        "You write concise executive-facing copy for warehouse and logistics leaders. "
        "Audience includes VPs and Directors of Operations/Supply Chain/Fulfillment. "
        "Stay factual: only use claims supported by the supplied context."
    )
    user = f"""Using ONLY the context below, follow these steps and output the final result as JSON.

**Step 1 - Extract risks**: From the context, identify all risk and observation statements.

**Step 2 - Rank risks**: Rank all extracted risks in descending order of operational severity. Select any one of the top 3 ranked risks randomly to anchor the teaser. 

**Step 3 - Write teaser**: Using the selected risk as the central theme, write 1 teaser that alludes to that risk while spelling it out completely, creating tension that pulls the reader into the full report.

Requirements for the teaser:
- **Goal**: Capture attention so the reader wants to open the full report, like a formal movie trailer, not a summary. Imply stakes or tension; its okay to list the risk in the teaser.
- **Length**: About 2 to 3 sentences, or roughly 40 to 50 words.
- **Tone**: Professional and punchy; curiosity without clickbait or hype; no jargon walls. Do not use em dashes.
- **Ending**: Must end with a direct, forward-pulling sentence that moves the reader to open the report. Examples of the right register: "This report separates what's working from what's quietly compounding." or "This report breaks down where [site] stands operationally and what the data says about the path forward."

Return **only** valid JSON: {{"teaser": "..."}}

Context:
{context}"""

    client = get_openai_client()
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.85 if attempt == 0 else 0.9,
                max_tokens=900,
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            single = data.get("teaser")
            if isinstance(single, str) and single.strip():
                return [single.strip()]
            alt = data.get("teasers")
            if not isinstance(alt, list):
                alt = []
            out: List[str] = []
            for t in alt:
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
            if len(out) >= 1:
                return out[:5]
            last_err = ValueError("Model returned no teaser text.")
        except Exception as e:
            last_err = e
            continue

    raise last_err if last_err else RuntimeError("Could not generate teaser variations.")
