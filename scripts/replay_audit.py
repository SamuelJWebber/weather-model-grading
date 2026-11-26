"""Run from repo root: python scripts/replay_audit.py. No network allowed."""
import sys
sys.path.insert(0, '.')
from wxgrade import snotel, coop
from wxgrade.decompose import run_decomposition_live

def forbidden(*args, **kwargs):
    raise RuntimeError('network forbidden during audit replay')
snotel.fetch_singlerun_hourly = forbidden
snotel.fetch_snwd_daily = forbidden
coop.fetch_snowd_daily = forbidden
for r in ('vail', 'breckenridge', 'park_city', 'palisades'):
    out = snotel.paired_snotel_leads_check(
        r, station=snotel.ELEVATION_MATCHED_STATIONS.get(r), allow_fetch=False)
    assert all(v['matches'] for v in out['identity_check_vs_preserved_artifact'].values())
    print(r, len(out['common_dates']), 'paired identity OK')
out = coop.paired_leads_check(allow_fetch=False)
assert all(v['matches'] for v in out['identity_check_vs_preserved_artifact'].values())
print('stowe', len(out['common_dates']), 'paired identity OK')
run_decomposition_live(allow_fetch=False)
print('decomposition replay OK')
