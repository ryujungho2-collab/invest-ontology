"""
하이브리드 역사: 시대 사건(data/world_events.csv) × 금융 상태(data/history_monthly.csv)
- 사건마다 '당시 시장 상태'와 '이후 12개월 결과'를 붙여 옵시디언 연표 노트로 만든다.
- 대시보드 타임라인용 데이터도 만든다.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / 'data' / 'history_monthly.csv'
EVENTS = ROOT / 'data' / 'world_events.csv'

STATE = [('cpi_yoy', '물가상승률', '%'), ('unrate', '실업률', 'lvl%'), ('curve', '장단기 금리차(10년-3개월)', '%p'),
         ('credit', '신용 스프레드(BAA-10년)', '%p'), ('real_rate', '실질금리(10년-물가)', '%p'),
         ('sp_dd', 'S&P500 고점 대비', '%'), ('cape', 'CAPE(실러 PER)', '')]
FWD = [('fwd_sp_12', 'S&P500'), ('fwd_bond_12', '미국 10년 국채'), ('fwd_gold_12', '금'), ('fwd_oil_12', '원유'),
       ('fwd_nasdaq_12', '나스닥'), ('fwd_sp_mdd_12', 'S&P500 12개월 내 최대낙폭')]


def load():
    h = pd.read_csv(HIST, index_col='month')
    ev = pd.read_csv(EVENTS, dtype=str).fillna('')
    return h, ev


def fmt(v, unit=''):
    if pd.isna(v):
        return '-'
    if unit == 'lvl%':                      # 수준값(부호 없이)
        return f'{v:.1f}%'
    return f'{v:+.1f}{unit}' if unit in ('%', '%p') else f'{v:.1f}'


def event_rows(h, ev):
    rows = []
    for _, e in ev.iterrows():
        m = e['month']
        s = h.loc[m] if m in h.index else None
        row = {k: e[k] for k in ev.columns}
        row['links'] = [x for x in e['links'].split(';') if x]
        if s is not None:
            row['state'] = {lab: fmt(s[c], u) for c, lab, u in STATE}
            row['recession'] = bool(s.get('recession') == 1)
            row['fwd'] = {lab: fmt(s[c], '%') for c, lab in FWD}
            row['fwd_sp_12'] = None if pd.isna(s['fwd_sp_12']) else round(float(s['fwd_sp_12']), 1)
        rows.append(row)
    return rows


def write_notes(write_note, link, vault, rows):
    for r in rows:
        name = f"{r['month']} {r['title']}"
        body = (f"# {name}\n\n{r['description']}\n\n분류: {r['category']} · 지역: {r['region']} · 성격: {r['kind']}\n"
                f"연결: " + ' '.join(link(x) for x in r['links']))
        auto = ['### 당시 시장 상태'] + [f'- {k}: {v}' for k, v in r.get('state', {}).items()]
        auto += [f"- 경기침체 중: {'예' if r.get('recession') else '아니오'}", '### 이후 12개월 결과']
        auto += [f'- {k}: {v}' for k, v in r.get('fwd', {}).items()] or ['- 아직 12개월이 지나지 않음']
        write_note(vault / '연표' / f'{name}.md', {'type': '연표', 'month': r['month'], 'category': r['category'],
                                                   'tags': '[연표]'}, body, '\n'.join(auto), section='시장 데이터')


def timeline(h, rows):
    """대시보드 타임라인: 월별 S&P500 총수익(로그 표시용), 경기침체, 사건 표시."""
    h = h[h.index >= '1950-01']
    return {'m': h.index.tolist(), 'sp': h['sp_tr'].round(3).tolist(), 'rec': h['recession'].fillna(0).astype(int).tolist(),
            'cpi': h['cpi_yoy'].round(2).where(h['cpi_yoy'].notna(), None).tolist(),
            'events': [{k: r.get(k) for k in ('month', 'title', 'category', 'kind', 'region', 'description', 'state', 'fwd', 'fwd_sp_12', 'recession', 'links')}
                       for r in rows]}
