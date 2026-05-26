def _normalise_theme(t):
    return (t or '').strip().lower().replace(' & ', ' and ')


def _normalise_country(c):
    return (c or '').strip().lower()


def _format_list(companies):
    names = [p['company'] for p in companies]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]}, {names[1]}, and {names[2]}"


def _geo_label(p):
    city    = (p.get('city') or '').strip()
    country = (p.get('country') or '').strip().split(',')[0].strip()
    return f"{city}, {country}" if city else country


def generate_why_us(lead, config):
    """
    Generate a Why Us sentence by matching the lead against portfolio companies.
    Returns empty string if no match found.
    Only call for leads where status != 'No fit'.
    """
    portfolio = config.get('portfolio', [])
    if not portfolio:
        return ''

    lead_theme   = _normalise_theme(lead.get('investmentTheme', ''))
    lead_country = _normalise_country(lead.get('country', ''))
    is_opportunistic = lead_theme == 'opportunistic'

    # Theme matches: up to 3 in list order (skip for opportunistic)
    theme_matches = []
    if not is_opportunistic:
        for p in portfolio:
            if _normalise_theme(p.get('themeFit', '')) == lead_theme:
                theme_matches.append(p)
            if len(theme_matches) == 3:
                break

    # Geo match: any portfolio company in lead's country
    geo_match = None
    for p in portfolio:
        countries = [_normalise_country(c) for c in (p.get('country') or '').split(',')]
        if lead_country in countries:
            geo_match = p
            break

    geo_in_theme = (
        geo_match is not None and
        any(p['company'] == geo_match['company'] for p in theme_matches)
    )

    parts = []

    # Theme sentence
    if theme_matches:
        theme_label = theme_matches[0].get('themeFit', lead_theme)
        company_list = _format_list(theme_matches)

        if geo_in_theme:
            local_name  = geo_match['company']
            local_label = _geo_label(geo_match)
            company_list = company_list.replace(
                local_name,
                f"{local_name} (based in {local_label})",
                1
            )
        parts.append(f"We've been backing players in the {theme_label} space — {company_list}.")

    # Geo sentence
    if geo_match and not geo_in_theme:
        prefix = "We're also active in" if parts else "We're active in"
        parts.append(f"{prefix} {_geo_label(geo_match)}: we invested in {geo_match['company']}.")

    return ' '.join(parts)
