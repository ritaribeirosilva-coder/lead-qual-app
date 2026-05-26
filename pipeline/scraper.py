import json
import re

try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPE_AVAILABLE = True
except ImportError:
    SCRAPE_AVAILABLE = False


def enrich_description(lead):
    """
    Scrape the lead's website to fill in a missing description.
    Modifies lead in place. Returns lead.
    """
    if lead.get('description') or not SCRAPE_AVAILABLE:
        return lead

    website = (lead.get('website') or '').strip()
    if not website:
        lead['description'] = '(no description found)'
        return lead

    url = website if website.startswith('http') else f'https://{website}'

    try:
        resp = requests.get(url, timeout=8, verify=False,
                            headers={'User-Agent': 'Mozilla/5.0'})
        html = resp.text
    except Exception:
        lead['description'] = '(no description found)'
        return lead

    soup = BeautifulSoup(html, 'html.parser')
    description = ''

    # 1. JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
            candidates = [data] + data.get('@graph', []) if isinstance(data, dict) else [data]
            for c in candidates:
                if isinstance(c, dict) and c.get('description', ''):
                    description = c['description'].strip()[:400]
                    break
        except Exception:
            pass
        if description:
            break

    # 2. og:description
    if not description:
        tag = soup.find('meta', property='og:description')
        if tag and tag.get('content', '').strip():
            description = tag['content'].strip()[:400]

    # 3. meta name="description"
    if not description:
        tag = soup.find('meta', attrs={'name': 'description'})
        if tag and tag.get('content', '').strip():
            description = tag['content'].strip()[:400]

    # 4. First h1
    if not description:
        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            description = h1.get_text(strip=True)[:200]

    # 5. First meaningful paragraph
    if not description:
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 60 and not re.search(r'cookie|privacy|accept|copyright', text, re.I):
                description = text[:400]
                break

    lead['description'] = description or '(no description found)'
    return lead
