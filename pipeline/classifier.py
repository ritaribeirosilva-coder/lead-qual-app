import json
import os

SYSTEM_PROMPT = """You are a classification assistant for a European VC fund investing at pre-seed and seed stage.

The fund has four investment themes:
- industrial tech: software or hardware sold primarily to manufacturers, industrial plants, or physical operations — predictive maintenance, MES, quality control, industrial IoT, automation, asset management
- energy transition: software sold to energy producers, grid operators, or large industrial emitters — grid management, battery optimisation, emissions tracking, energy storage, renewable energy infrastructure
- supply chain and logistics: software sold to shippers, logistics operators, or procurement teams at industrial or manufacturing companies — route optimisation, freight visibility, warehouse management, procurement, trade compliance
- vertical software: specialised software built for a specific industry vertical with a clearly defined B2B buyer — not horizontal SaaS, not consumer

Classification rules:
1. Assign a theme only if the company's PRIMARY buyer matches that theme's profile — do not classify by technology alone.
2. B2B software with no specific industrial buyer (cybersecurity, CRM, analytics, HR tech, fintech tools, general AI tooling, etc.) → opportunistic.
3. Healthcare, biotech, or pharma solutions (drug development, medical devices, clinical treatments, cell therapy, diagnostics) → excluded. Software that sells TO healthcare/pharma as customers may be opportunistic or vertical software.
4. Products sold primarily to individuals rather than businesses → excluded.
5. When in doubt: if the buyer is any kind of business → default to opportunistic, not excluded.

Always return a valid JSON array. Start immediately with [ — no other characters before it."""


def _build_company_entry(i, lead):
    lines = [
        f"{i}. Name: {lead.get('name', '')}",
        f"   Website: {lead.get('website', '')}",
        f"   Description: {lead.get('description', '')}",
    ]
    if lead.get('sector'):
        lines.append(f"   Sector: {lead['sector']}")
    return '\n'.join(lines)


def _classify_batch(batch, client):
    count = len(batch)
    companies = '\n\n'.join(_build_company_entry(i + 1, lead) for i, lead in enumerate(batch))

    user_prompt = f"""Classify ALL {count} companies listed below.

{companies}

Return ONLY a valid JSON array with EXACTLY {count} objects in the same order. No text before or after.

Example for 3 companies:
[
  {{ "investmentTheme": "industrial tech", "themeJustification": "one sentence" }},
  {{ "investmentTheme": "opportunistic", "themeJustification": "" }},
  {{ "investmentTheme": "excluded", "themeJustification": "" }}
]

Allowed values: industrial tech | energy transition | supply chain and logistics | vertical software | opportunistic | excluded"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content or ''

    # Strip markdown fences
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('```')[1]
        cleaned = cleaned.lstrip('json').strip()

    try:
        results = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[classifier] JSON parse failed. Raw: {raw[:200]}")
        return None

    if not isinstance(results, list):
        results = list(results.values()) if isinstance(results, dict) else None

    if results is None or len(results) != count:
        print(f"[classifier] Length mismatch: expected {count}, got {len(results) if results else 'None'}")
        return None

    return results


def classify_leads(leads, config):
    """
    Classify a list of qualifiable leads using the OpenAI API.
    Adds investmentTheme and themeJustification to each lead.
    Returns the updated list.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        for lead in leads:
            lead['investmentTheme'] = 'unclassified'
            lead['themeJustification'] = 'No API key configured'
        return leads

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        for lead in leads:
            lead['investmentTheme'] = 'unclassified'
            lead['themeJustification'] = 'openai package not installed'
        return leads

    chunk_size = 15
    for i in range(0, len(leads), chunk_size):
        batch = leads[i:i + chunk_size]
        results = _classify_batch(batch, client)

        if results is None:
            for lead in batch:
                lead['investmentTheme'] = 'error'
                lead['themeJustification'] = 'parse error'
        else:
            for lead, res in zip(batch, results):
                lead['investmentTheme']    = res.get('investmentTheme', 'error')
                lead['themeJustification'] = res.get('themeJustification', '')

    return leads
