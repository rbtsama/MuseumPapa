"""Schema-lock test: seasonal:* exclusion tags must be 'seasonal:Mon-Mon' format."""
import glob
import json
import re

import pytest

MONTH_TOKEN = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
SEASONAL_RE = re.compile(rf'^seasonal:{MONTH_TOKEN}-{MONTH_TOKEN}$')


def test_all_seasonal_tags_match_month_range_format():
    bad = []
    for f in glob.glob('data/raw/pass_policies/*.json'):
        with open(f, encoding='utf-8') as fh:
            d = json.load(fh)
        for t in d.get('exclusions') or []:
            if isinstance(t, str) and t.startswith('seasonal:'):
                if not SEASONAL_RE.match(t):
                    bad.append((f, t))
    if bad:
        msg = '\n'.join(f'  {f}: {t}' for f, t in bad)
        pytest.fail(f'{len(bad)} seasonal tags violate Mon-Mon format:\n{msg}')
