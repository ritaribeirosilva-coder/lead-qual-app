import csv
import io
import zipfile
from datetime import datetime

# Exact CSV headers requested
HEADERS = [
    'name', 'website', 'Lead description', 'Lead Stage', 'country', 'source',
    'dateAdded', 'processingStatus', 'Lead Round Size', 'roundDisclosed',
    'siftedStage', 'sectors', 'prioGeo', 'secondPrioGeo', 'rightStage',
    'Investment Theme', 'Theme Justification', 'Priority', 'Owners', 'Why Us?', 'Status'
]

HIGH_FIT_STATUSES    = {'High priority', 'High fit'}
OPPORTUNISTIC_STATUSES = {'Moderate fit', 'Low fit'}
NO_FIT_STATUSES      = {'No fit'}


def _row(lead, date_added):
    return [
        lead.get('name', ''),
        lead.get('website', ''),
        lead.get('description', ''),
        lead.get('investmentStage', ''),
        lead.get('country', ''),
        lead.get('source', ''),
        date_added,
        lead.get('status', ''),               # processingStatus
        lead.get('dealSize', '') or '',
        lead.get('roundDisclosed', '') or '',
        lead.get('siftedStage', '') or '',
        lead.get('sector', '') or '',
        lead.get('prioGeo', '') or '',
        lead.get('secondPrioGeo', '') or '',
        lead.get('rightStage', '') or '',
        lead.get('investmentTheme', '') or '',
        lead.get('themeJustification', '') or '',
        lead.get('status', ''),               # Priority (same label)
        lead.get('owner', '') or '',
        lead.get('whyUs', '') or '',
        'Open',
    ]


def _make_csv(leads, date_added):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    for lead in leads:
        w.writerow(_row(lead, date_added))
    return buf.getvalue().encode('utf-8-sig')  # utf-8-sig for Excel compatibility


def build_export_zip(result, run_name=None):
    """
    Build a ZIP containing three CSVs from a result dict.
    Returns bytes ready to send as a file download.
    """
    leads      = result.get('leads', [])
    date_added = result.get('timestamp', datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
    prefix     = run_name or result.get('run_name') or result.get('filename', 'run').replace('.csv', '')

    high_fit      = [l for l in leads if l.get('status') in HIGH_FIT_STATUSES]
    opportunistic = [l for l in leads if l.get('status') in OPPORTUNISTIC_STATUSES]
    no_fit        = [l for l in leads if l.get('status') in NO_FIT_STATUSES]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'{prefix}_high_fit.csv',      _make_csv(high_fit, date_added))
        zf.writestr(f'{prefix}_opportunistic.csv', _make_csv(opportunistic, date_added))
        zf.writestr(f'{prefix}_no_fit.csv',        _make_csv(no_fit, date_added))

    return zip_buf.getvalue()
