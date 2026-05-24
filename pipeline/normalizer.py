import csv
import io
import re
import uuid
from datetime import datetime, timezone


def normalize_csv(file_stream, source, config, uploader_name):
    """
    Parse and normalize a CSV file into canonical Lead objects.

    Args:
        file_stream: file-like object (from request.files['file'].stream)
        source: 'Sifted' or 'PitchBook'
        config: dict loaded from config.json
        uploader_name: full name of the logged-in user

    Returns:
        {
            'leads': [...],
            'warnings': [...],
            'run_id': str,
            'uploaded_by': str,
            'source': str,
            'row_count': int
        }
    """
    run_id = str(uuid.uuid4())
    date_added = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    warnings = []
    leads = []

    # Read raw bytes and decode (utf-8 with latin-1 fallback)
    raw = file_stream.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')

    column_mappings = config.get('column_mappings', {})
    source_map = column_mappings.get(source, {})
    country_aliases = config.get('country_aliases', {})

    reader = csv.DictReader(io.StringIO(text))
    file_headers = reader.fieldnames or []

    # Warn about missing mapped columns upfront
    warned_cols = set()
    for canonical_field, source_col in source_map.items():
        if source_col and source_col not in file_headers and source_col not in warned_cols:
            warnings.append(f"Column '{source_col}' not found in file for field '{canonical_field}'")
            warned_cols.add(source_col)

    for row in reader:
        lead = _build_lead(
            row, source, source_map, country_aliases,
            run_id, date_added, uploader_name
        )
        leads.append(lead)

    return {
        'leads': leads,
        'warnings': warnings,
        'run_id': run_id,
        'uploaded_by': uploader_name,
        'source': source,
        'row_count': len(leads),
    }


def _build_lead(row, source, source_map, country_aliases, run_id, date_added, uploader_name):
    def get(field, default=''):
        col = source_map.get(field)
        if not col:
            return default
        return (row.get(col) or '').strip()

    # --- name, website, description ---
    name = get('name')
    website = _normalize_website(get('website'))
    description = get('description')

    # --- country ---
    raw_country = get('country')
    if source == 'PitchBook':
        # "Amsterdam, Netherlands" → "Netherlands"
        raw_country = raw_country.split(',')[-1].strip()
    country = _normalize_country(raw_country, country_aliases)

    # --- investmentStage ---
    if source == 'PitchBook':
        investment_stage = get('investmentStage')
    else:
        investment_stage = ''  # derived later by filter step

    # --- Sifted-specific fields ---
    deal_size = 0.0
    round_disclosed = ''
    sifted_stage = ''
    sector = ''

    if source == 'Sifted':
        raw_deal_size = get('dealSize')
        deal_size = _parse_deal_size(raw_deal_size)
        round_disclosed = get('roundDisclosed')
        sifted_stage = get('siftedStage')
        sector = get('sector')

    return {
        'name': name,
        'website': website,
        'description': description,
        'investmentStage': investment_stage,
        'country': country,
        'source': source,
        'dateAdded': date_added,
        'processingStatus': 'pending',
        'dealSize': deal_size,
        'roundDisclosed': round_disclosed,
        'siftedStage': sifted_stage,
        'sector': sector,
        'uploadedBy': uploader_name,
        'runId': run_id,
    }


def _normalize_website(url):
    url = url.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url


def _normalize_country(raw, aliases):
    if not raw:
        return ''
    key = raw.strip().lower()
    return aliases.get(key, raw.strip().title())


def _parse_deal_size(raw):
    cleaned = re.sub(r'[^0-9.]', '', str(raw))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0
