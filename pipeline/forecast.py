"""
예측 엔진: '지금과 닮은 과거'의 이후 결과 분포로 미래를 확률로 읽는다 (유사 국면 / analog 방법).

원칙
- 상태 변수는 그 달에 알 수 있던 값만 쓴다. 이후 수익률(fwd_*)은 정답으로만 쓴다.
- 과거 시점 검증(walk-forward): 각 달 t에서 't 이전 12개월 이상 지나 결과가 확정된 달'만 후보로 쓴다.
- 기준선(기저율)보다 나은지 채점한다. 못 이기면 '실력 없음'으로 표시한다.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / 'data' / 'history_monthly.csv'
LOG = ROOT / 'data' / 'forecasts.csv'

FEATURES = {  # 이름: (설명, 변환)
    'cpi_yoy': '물가상승률', 'unrate_gap': '실업률 추세(12개월 평균 대비)', 'curve': '장단기 금리차',
    'credit': '신용 스프레드', 'real_rate': '실질금리', 'oil_yoy': '유가 1년 변화',
    'sp_trend': '주가 10개월선 대비', 'sp_mom12': '주가 1년 수익률', 'sp_dd': '주가 고점 대비', 'log_cape': '밸류에이션(log CAPE)',
}
TARGETS = {'fwd_sp_12': 'S&P500', 'fwd_bond_12': '미국 10년 국채', 'fwd_gold_12': '금', 'fwd_oil_12': '원유',
           'fwd_nasdaq_12': '나스닥', 'fwd_sp_mdd_12': 'S&P500 12개월 내 최대낙폭'}
K, PER_YEAR = 20, 3


def load():
    h = pd.read_csv(HIST, index_col='month')
    h.index = pd.PeriodIndex(h.index, freq='M')
    # 실업률 발표가 빠진 달(예: 2025년 10월 정부 셧다운)이 있어도 12개월 평균이 끊기지 않게
    h['unrate_gap'] = h['unrate'] - h['unrate'].rolling(12, min_periods=9).mean()
    # CAPE 원자료가 끊긴 최근 달: 분모(10년 평균 실질이익)를 직전 5년 성장률로 늘려 근사
    cape = h['cape'].copy()
    last = cape.last_valid_index()
    if last is not None and last < h.index[-1]:
        e10 = h['sp_price'] / cape                                   # 10년 평균이익(가격 단위)
        g = (e10[last] / e10[last - 60]) ** (1 / 60) if not pd.isna(e10.get(last - 60)) else 1.0
        later = h.index[h.index > last]
        steps = np.array([(m - last).n for m in later])
        cape.loc[later] = h.loc[later, 'sp_price'].values / (e10[last] * g ** steps)
    h['cape'] = cape
    h['log_cape'] = np.log(h['cape'])
    # 발표 지연 등으로 최근 몇 달이 비면 직전 값으로 (최대 3개월)
    h[list(FEATURES)] = h[list(FEATURES)].ffill(limit=3)
    return h


def _pick(dist, months, k=K, per_year=PER_YEAR):
    order = np.argsort(dist)
    chosen, per = [], {}
    for i in order:
        y = months[i].year
        if per.get(y, 0) >= per_year:
            continue
        chosen.append(i)
        per[y] = per.get(y, 0) + 1
        if len(chosen) >= k:
            break
    return chosen


def analogs_at(h, t, k=K):
    """시점 t(Period)의 상태와 닮은 과거 달. t에서 결과가 확정된 달(t-12 이전)만 후보."""
    X = h[list(FEATURES)]
    pool = X[(X.index <= t - 12)].dropna()
    if len(pool) < 60 or t not in X.index or X.loc[t].isna().any():
        return None
    mu, sd = pool.mean(), pool.std()            # 그 시점까지의 정보로만 표준화
    z = (pool - mu) / sd
    q = (X.loc[t] - mu) / sd
    dist = np.sqrt(((z - q) ** 2).sum(axis=1)).values
    idx = _pick(dist, list(pool.index), k)
    sel = pool.index[idx]
    return pd.DataFrame({'month': sel, 'dist': dist[idx]}).set_index('month')


def summarize(h, sel):
    out = {}
    for c, name in TARGETS.items():
        v = h.loc[sel.index, c].dropna()
        if len(v) < 5:
            continue
        out[name] = {'n': int(len(v)), 'p_up': float((v > 0).mean()), 'median': float(v.median()),
                     'p10': float(v.quantile(0.1)), 'p90': float(v.quantile(0.9)), 'mean': float(v.mean())}
    return out


def walk_forward(h, start='1975-01', target='fwd_sp_12'):
    """매달 그 시점 정보만으로 예측 → 실제와 비교. 기준선 = 그 시점까지의 전체 평균 상승확률·평균수익."""
    rows = []
    for t in h.index[(h.index >= pd.Period(start, 'M'))]:
        actual = h.at[t, target] if t in h.index else np.nan
        if pd.isna(actual):
            continue
        sel = analogs_at(h, t)
        if sel is None:
            continue
        v = h.loc[sel.index, target].dropna()
        past = h.loc[h.index <= t - 12, target].dropna()
        rows.append({'month': t, 'pred_p': (v > 0).mean(), 'pred_med': v.median(),
                     'base_p': (past > 0).mean(), 'base_mean': past.mean(), 'actual': actual})
    return pd.DataFrame(rows).set_index('month')


def score(wf):
    up = (wf['actual'] > 0).astype(float)
    brier = ((wf['pred_p'] - up) ** 2).mean()
    brier_base = ((wf['base_p'] - up) ** 2).mean()
    ic = wf['pred_med'].corr(wf['actual'], method='spearman')
    low = wf[wf['pred_p'] < 0.5]['actual']
    high = wf[wf['pred_p'] >= 0.7]['actual']
    return {'months': int(len(wf)), 'brier': round(float(brier), 4), 'brier_base': round(float(brier_base), 4),
            'skill': round(float(1 - brier / brier_base), 3),          # >0 이면 기저율보다 나음
            'ic': round(float(ic), 3),                                   # 예측 중간값과 실제의 순위상관
            'hit': round(float(((wf['pred_p'] >= 0.5) == (up == 1)).mean()), 3),
            'low_n': int(len(low)), 'low_avg': round(float(low.mean()), 1) if len(low) else None,
            'high_n': int(len(high)), 'high_avg': round(float(high.mean()), 1) if len(high) else None,
            'all_avg': round(float(wf['actual'].mean()), 1)}


def current(h, events_csv=ROOT / 'data' / 'world_events.csv'):
    """가장 최근 달의 예측 + 닮은 달과 그 시기 연표 사건."""
    X = h[list(FEATURES)].dropna()
    t = X.index[-1]
    sel = analogs_at(h, t)
    ev = pd.read_csv(events_csv, dtype=str).fillna('')
    ev['p'] = pd.PeriodIndex(ev['month'], freq='M')
    analogs = []
    for m, r in sel.iterrows():
        near = ev[(ev['p'] >= m - 3) & (ev['p'] <= m + 3)]
        analogs.append({'month': str(m), 'dist': round(float(r['dist']), 2),
                        'state': {FEATURES[f]: round(float(h.at[m, f]), 1) for f in FEATURES},
                        'fwd': {TARGETS[c]: (None if pd.isna(h.at[m, c]) else round(float(h.at[m, c]), 1)) for c in TARGETS},
                        'events': [f"{e['month']} {e['title']}" for _, e in near.iterrows()]})
    return {'as_of': str(t), 'state': {FEATURES[f]: round(float(X.at[t, f]), 2) for f in FEATURES},
            'summary': summarize(h, sel), 'analogs': analogs}


def long_term(h, start='1975-01'):
    """밸류에이션(CAPE) → 향후 10년 S&P500 연평균 수익률. 각 시점 이전 정보로만 회귀(walk-forward)."""
    tr = h['sp_tr']
    h = h.assign(fwd_sp_120=((tr.shift(-120) / tr) ** (1 / 10) - 1) * 100)
    d = h[['log_cape', 'fwd_sp_120']].dropna()
    preds = []
    for t in d.index[d.index >= pd.Period(start, 'M')]:
        past = d[d.index <= t - 120]
        if len(past) < 120:
            continue
        b = np.polyfit(past['log_cape'], past['fwd_sp_120'], 1)
        preds.append({'month': str(t), 'pred': float(np.polyval(b, d.at[t, 'log_cape'])),
                      'base': float(past['fwd_sp_120'].mean()), 'actual': float(d.at[t, 'fwd_sp_120'])})
    p = pd.DataFrame(preds)
    skill = 1 - ((p.pred - p.actual) ** 2).mean() / ((p.base - p.actual) ** 2).mean()
    b = np.polyfit(d['log_cape'], d['fwd_sp_120'], 1)
    resid = (d['fwd_sp_120'] - np.polyval(b, d['log_cape'])).std()
    t = h['log_cape'].dropna().index[-1]
    now = float(np.polyval(b, h.at[t, 'log_cape']))
    return {'as_of': str(t), 'cape': round(float(np.exp(h.at[t, 'log_cape'])), 1), 'expected': round(now, 1),
            'low': round(float(now - resid), 1), 'high': round(float(now + resid), 1), 'hist_avg': round(float(d['fwd_sp_120'].mean()), 1),
            'skill': round(float(skill), 2), 'corr': round(float(p.pred.corr(p.actual)), 2), 'months': int(len(p)),
            'series': {'m': p['month'].tolist()[::3], 'pred': p['pred'].round(1).tolist()[::3], 'actual': p['actual'].round(1).tolist()[::3]}}


def scorecard(h):
    """단기(12개월) 유사국면 예측의 과거 시점 채점."""
    out = {}
    for tgt in ['fwd_sp_12', 'fwd_bond_12', 'fwd_gold_12', 'fwd_oil_12']:
        out[TARGETS[tgt]] = score(walk_forward(h, target=tgt))
    return out


def log_forecast(fc):
    """오늘 예측을 기록하고, 12개월이 지난 예측은 실제 결과로 채점."""
    h = load()
    rows = [{'made': str(pd.Timestamp.today().date()), 'as_of': fc['as_of'], 'asset': a,
             'p_up': round(s['p_up'], 3), 'median': round(s['median'], 2)} for a, s in fc['summary'].items()]
    log = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame(columns=['made', 'as_of', 'asset', 'p_up', 'median', 'actual'])
    log = log[log['as_of'] != fc['as_of']]           # 같은 기준월 예측은 최신으로 교체
    log = pd.concat([log, pd.DataFrame(rows)], ignore_index=True)
    col = {v: k for k, v in TARGETS.items()}
    for i, r in log.iterrows():
        m = pd.Period(r['as_of'], 'M')
        c = col.get(r['asset'])
        if c and m in h.index and not pd.isna(h.at[m, c]):
            log.at[i, 'actual'] = round(float(h.at[m, c]), 2)
    LOG.parent.mkdir(exist_ok=True)
    log.to_csv(LOG, index=False)
    return log


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    h = load()
    for tgt in ['fwd_sp_12', 'fwd_bond_12', 'fwd_gold_12', 'fwd_oil_12']:
        wf = walk_forward(h, target=tgt)
        print(TARGETS[tgt], score(wf))
    fc = current(h)
    print('기준월', fc['as_of'], fc['state'])
    for a, s in fc['summary'].items():
        print(f"  {a}: 상승확률 {s['p_up']:.0%}  중간값 {s['median']:+.1f}%  범위 {s['p10']:+.1f}~{s['p90']:+.1f}%")
    for a in fc['analogs'][:8]:
        print('  ', a['month'], a['dist'], 'S&P', a['fwd']['S&P500'], '|', '; '.join(a['events'])[:90])
