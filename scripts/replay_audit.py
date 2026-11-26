"""Run from repo root: python scripts/replay_audit.py. No network/writes to source."""
import json
import shutil
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, '.')
from wxgrade import snotel, coop
from wxgrade.decompose import run_decomposition_live

def forbidden(*args, **kwargs):
    raise RuntimeError('network forbidden during audit replay')
snotel.fetch_singlerun_hourly = forbidden
snotel.fetch_snwd_daily = forbidden
coop.fetch_snowd_daily = forbidden
with tempfile.TemporaryDirectory() as temp:
    output = Path(temp) / 'results'
    shutil.copytree('results', output)
    for r in ('vail', 'breckenridge', 'park_city', 'palisades', 'stowe'):
        artifact = next(Path('results').glob(f'grading_{r}_*paired*2026-11-24.json'))
        expected = json.loads(artifact.read_text())
        if r == 'stowe':
            out = coop.paired_leads_check(output_dir=output, allow_fetch=False)
        else:
            out = snotel.paired_snotel_leads_check(
                r, station=snotel.ELEVATION_MATCHED_STATIONS.get(r),
                output_dir=output, allow_fetch=False)
        assert all(v['matches'] for v in out['identity_check_vs_preserved_artifact'].values())
        assert out['paired_scores'] == expected['paired_scores']
        assert out['common_dates'] == expected['common_dates']
        print(r, len(out['common_dates']), 'paired identity OK')
    out=run_decomposition_live(output_dir=output,allow_fetch=False)
    expected=json.loads(Path('results/decomposition_2026-11-26.json').read_text())
    for r,value in out['resorts'].items():
        assert value['overall_paired']==expected['resorts'][r]['overall_paired']
    print('decomposition replay OK; source artifacts unchanged')
