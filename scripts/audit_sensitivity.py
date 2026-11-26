"""Saved-input sensitivity checks. Run from repo root, no network.

Supplement only, defined after inspecting original sample. Bootstrap
resamples days independently and ignores serial correlation; intervals
are descriptive, not validated inference or a forward test.
"""
import itertools
import json
import math
import random
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, '.')
from wxgrade.grade import LOCATIONS, persistence_baseline
from wxgrade.snotel import RESORT_STATIONS, ELEVATION_MATCHED_STATIONS
from wxgrade.coop import COOP_STATIONS
from wxgrade.decompose import overall_paired_scores

MODELS = ('gfs_seamless', 'icon_seamless', 'ecmwf_ifs025')

def corr(a,b):
    x=[v-statistics.mean(a) for v in a];y=[v-statistics.mean(b) for v in b]
    den=math.sqrt(sum(v*v for v in x)*sum(v*v for v in y))
    return sum(u*v for u,v in zip(x,y))/den if den else None

def ranks(a):
    return [1+sum(v<x for v in a)+(sum(v==x for v in a)-1)/2 for x in a]

def correlation_cells(actual, series, draws=2000):
    result={};rng=random.Random(31)
    for a,b in itertools.combinations(MODELS,2):
        days=sorted(set(actual)&set(series[a])&set(series[b]))
        x=[series[a][d]-actual[d] for d in days]
        y=[series[b][d]-actual[d] for d in days]
        bs=[]
        for _ in range(draws):
            ids=[rng.randrange(len(days)) for _ in days]
            value=corr([x[i] for i in ids],[y[i] for i in ids])
            if value is not None:bs.append(value)
        bs.sort()
        result[f'{a} vs {b}']={'n':len(days),'pearson':corr(x,y),
            'spearman':corr(ranks(x),ranks(y)),
            'iid_day_bootstrap_95pct':[bs[int(.025*len(bs))],bs[min(len(bs)-1,int(.975*len(bs)))]] if bs else None,
            'valid_bootstrap_draws':len(bs),'requested_draws':draws}
    return result

def deadband(a):
    out={};last=None;prior=None
    for d,v in sorted(a.items()):
        if prior is not None and (date.fromisoformat(d)-date.fromisoformat(prior)).days != 1:
            last=None
        prior=d
        if last is None or abs(v-last)>0.0254+1e-9:last=v
        out[d]=last
    return out

def trailing_median(a):
    out={}
    for d in sorted(a):
        days=[(date.fromisoformat(d)-timedelta(days=i)).isoformat() for i in range(3)]
        if all(x in a for x in days):out[d]=statistics.median(a[x] for x in days)
    return out

original=json.loads(Path('results/decomposition_2026-11-26.json').read_text())
out={'basis':'Post-audit exploratory sensitivity only. No original definition changed. Smoothed/deadband depth is a different target, not sensor truth. Bootstrap assumes independent days although snowpack is serially correlated; intervals are descriptive and may be too narrow.', 'bootstrap_seed':31,'resorts':{}}
for r, meta in original['resorts'].items():
    st=COOP_STATIONS[r] if r=='stowe' else ELEVATION_MATCHED_STATIONS.get(r,RESORT_STATIONS[r])
    actual=json.loads(Path(meta['actuals_saved_to']).read_text())['values']
    grid=st if r=='stowe' else LOCATIONS[r]
    valid=21 if r=='stowe' else 8
    start,end=meta['window'];dates=[d for d in actual if start<=d<=end]
    series={}
    for model in MODELS:
        pred={}
        for d in dates:
            path=Path('results/raw/singleruns')/f"{grid['lat']:.4f}_{grid['lon']:.4f}_{model}_{d}.json"
            run=json.loads(path.read_text());key=f'{d}T{valid:02d}:00'
            if key in run:pred[d]=run[key]
        series[model]=pred
    common=set.intersection(*(set(v) for v in series.values()))
    series['ensemble_mean_3']={d:sum(series[m][d] for m in MODELS)/3 for d in common}
    sensitivity={}
    for name, target in [('raw',actual),('one_inch_deadband',deadband(actual)),('trailing_three_day_median',trailing_median(actual))]:
        sensitivity[name]=overall_paired_scores(target,{**series,'persistence_same_target':persistence_baseline(target,1)})
    all_target_days=set.intersection(*(set(t) for t in [actual,deadband(actual),trailing_median(actual)]))
    same_days=set(all_target_days)
    for target in [actual,deadband(actual),trailing_median(actual)]:
        same_days &= set(persistence_baseline(target,1))
    fixed={}
    for name,target in [('raw',actual),('one_inch_deadband',deadband(actual)),('trailing_three_day_median',trailing_median(actual))]:
        fixed[name]=overall_paired_scores(
            {d:target[d] for d in same_days},
            {**series,'persistence_same_target':persistence_baseline(target,1)})
    out['resorts'][r]={'correlations':correlation_cells(actual,series),
                      'target_sensitivity':sensitivity,
                      'sensitivity_common_dates':sorted(same_days),
                      'target_sensitivity_same_dates':fixed}
Path('results/audit_sensitivity_2026-11-26.json').write_text(json.dumps(out,indent=2))
for r,v in out['resorts'].items():
 print(r, {k:(c['ensemble_mean_3']['n'],round(c['ensemble_mean_3']['mae']/0.0254,2),round(c['persistence_same_target']['mae']/0.0254,2)) for k,c in v['target_sensitivity'].items()})
