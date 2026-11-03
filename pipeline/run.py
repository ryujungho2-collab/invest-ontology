"""
투자 온톨로지 일일 파이프라인
  1) 시장 가격(Yahoo) → 전략 신호        2) 거시 지표(FRED) → 국면 판단
  3) 국면 → 닮은 역사 국면 연결          4) 옵시디언 노트 갱신 + 일일 브리핑 노트
  5) 텔레그램 전송 (환경변수 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID가 있을 때)

로컬:  python pipeline/run.py --dry-run
GitHub Actions: .github/workflows/daily.yml이 매일 실행
"""
import argparse
import io
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import seeds as S

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / 'vault'
AUTO_START, AUTO_END = '<!-- 자동 갱신 시작 -->', '<!-- 자동 갱신 끝 -->'


# ---------------------------------------------------------------- 데이터
def load_prices():
    tickers = sorted(set(S.ASSETS) | {C.CASH_TICKER})
    px = yf.download(tickers, period='3y', auto_adjust=True, progress=False)['Close'].dropna(how='all')
    now_et = pd.Timestamp.now(tz='America/New_York')
    if now_et.hour < 16 and px.index[-1].date() == now_et.date():
        px = px.iloc[:-1]                      # 장중 미완성 봉 제외
    return px.ffill()


def load_fred():
    out = {}
    for sid in C.FRED:
        try:
            r = requests.get(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}', timeout=30)
            df = pd.read_csv(io.StringIO(r.text))
            s = pd.to_numeric(df.iloc[:, 1], errors='coerce')
            s.index = pd.to_datetime(df.iloc[:, 0])
            out[sid] = s.dropna()
        except Exception as e:                  # 지표 하나 실패해도 나머지는 진행
            print(f'FRED {sid} 실패: {e}')
    return out


# ---------------------------------------------------------------- 전략 신호
def is_month_end(day):
    return (day + CustomBusinessDay(calendar=USFederalHolidayCalendar())).month != day.month


def best_defensive(px, day):
    me = px.groupby(px.index.to_period('M')).tail(1)
    if not is_month_end(day):
        me = me[me.index.to_period('M') < day.to_period('M')]
    m = me.rename(columns={C.CASH_TICKER: 'CASH'})
    score = ((m.iloc[-1] / m.iloc[-4] - 1) + (m.iloc[-1] / m.iloc[-7] - 1))[C.DEFENSIVE] / 2
    best = score.idxmax()
    pick = best if score[best] > 0 else 'CASH'
    return C.CASH_TICKER if pick == 'CASH' else pick


def strategy_targets(px, strat):
    day = px.index[-1]
    defensive = best_defensive(px, day)
    total, sleeves = {}, {}
    for asset, w in strat['weights'].items():
        if asset not in strat['trend']:
            total[asset] = total.get(asset, 0) + w
            continue
        base, cap = strat['trend'][asset]
        p, sma = px[base], px[base].rolling(C.SMA_DAYS).mean()
        on = False
        for d in px.index:                      # 3% 밴드 상태를 과거부터 이어서 계산
            if np.isnan(sma[d]): on = False
            elif on and p[d] < sma[d] * (1 - C.BAND): on = False
            elif not on and p[d] > sma[d] * (1 + C.BAND): on = True
        vol = px[asset].pct_change().iloc[-C.VOL_DAYS:].std() * np.sqrt(252)
        x = round(min(1.0, cap / vol) * 5) / 5 if on else 0.0
        hold = ({asset: x, **({C.CASH_TICKER: 1 - x} if x < 1 else {})} if on else {defensive: 1.0})
        sleeves[asset] = {'on': on, 'base': base, 'gap': float(p.iloc[-1] / sma.iloc[-1] - 1),
                          'vol': float(vol), 'hold': hold}
        for t, v in hold.items():
            total[t] = total.get(t, 0) + v * w
    return day, sleeves, total, defensive


# ---------------------------------------------------------------- 거시 국면
def macro_state(fred):
    st, flags = {}, []
    if 'UNRATE' in fred:
        u = fred['UNRATE']; ma = u.rolling(12).mean()
        st['실업률'] = f'{u.iloc[-1]:.1f}% (12개월 평균 {ma.iloc[-1]:.2f}%, {u.index[-1]:%Y-%m})'
        if u.iloc[-1] > ma.iloc[-1]: flags.append('경기둔화')
    if 'CPIAUCSL' in fred:
        c = fred['CPIAUCSL']; yoy = (c.iloc[-1] / c.iloc[-13] - 1) * 100
        st['물가상승률'] = f'{yoy:.1f}% 전년비 ({c.index[-1]:%Y-%m})'
        if yoy >= 4: flags.append('고물가')
    if 'T10Y2Y' in fred:
        v = fred['T10Y2Y'].iloc[-1]; st['장단기 금리차'] = f'{v:+.2f}%p'
        if v < 0: flags.append('금리역전')
    if 'BAA10Y' in fred:
        v = fred['BAA10Y'].iloc[-1]; st['신용 스프레드'] = f'{v:.2f}%p'
        if v >= 3: flags.append('신용경색')
    if 'DCOILWTICO' in fred:
        o = fred['DCOILWTICO']; chg = (o.iloc[-1] / o.iloc[-22] - 1) * 100 if len(o) > 22 else np.nan
        st['WTI 유가'] = f'${o.iloc[-1]:.1f} (1개월 {chg:+.1f}%)'
    if 'DTWEXBGS' in fred:
        d = fred['DTWEXBGS']; chg = (d.iloc[-1] / d.iloc[-22] - 1) * 100 if len(d) > 22 else np.nan
        st['달러 지수'] = f'{d.iloc[-1]:.1f} (1개월 {chg:+.1f}%)'
    analogs = [name for name, h in S.HISTORY.items() if flags and set(h['regime']) & set(flags)]
    return st, flags, analogs


# ---------------------------------------------------------------- 옵시디언 노트
def write_note(path, frontmatter, static_body, auto_body, section='현재 상태'):
    path.parent.mkdir(parents=True, exist_ok=True)
    auto = f'{AUTO_START}\n{auto_body.strip()}\n{AUTO_END}'
    if path.exists():                            # 사람이 쓴 부분은 보존, 자동 구간만 교체
        text = path.read_text(encoding='utf-8')
        if AUTO_START in text and AUTO_END in text:
            text = re.sub(re.escape(AUTO_START) + '.*?' + re.escape(AUTO_END), lambda _: auto, text, flags=re.S)
            path.write_text(text, encoding='utf-8')
            return
    fm = '---\n' + '\n'.join(f'{k}: {v}' for k, v in frontmatter.items()) + '\n---\n'
    path.write_text(fm + static_body.strip() + f'\n\n## {section}\n' + auto + '\n', encoding='utf-8')


def link(x):
    return f'[[{x}]]'


def build_vault(px, day, strat, sleeves, total, defensive, macro, flags, analogs):
    holdings = {t for t, w in total.items() if w > 0.001}
    for t, a in S.ASSETS.items():
        if t not in px: continue
        p = px[t]; sma = p.rolling(C.SMA_DAYS).mean()
        auto = [f'- 기준일: {day.date()}', f'- 종가: {p.iloc[-1]:,.2f}',
                f'- 200일선 대비: {p.iloc[-1] / sma.iloc[-1] - 1:+.1%}',
                f'- 1개월 수익률: {p.iloc[-1] / p.iloc[-22] - 1:+.1%}',
                f'- 내 목표 비중: {total.get(t, 0):.1%}' + (' ✅ 보유' if t in holdings else '')]
        if t in sleeves:
            s = sleeves[t]
            auto.append(f"- 신호: {'보유' if s['on'] else '청산'} (기준 {link(s['base'])} 200일선 대비 {s['gap']:+.1%}, 변동성 {s['vol']:.0%})")
        body = (f"# {t} · {a['name']}\n\n노출: " + ' '.join(link(e) for e in a['exposure']) +
                (f"\n신호 기준: {link(a['signal_of'])}" if a['signal_of'] else ''))
        write_note(VAULT / '자산' / f'{t}.md', {'type': '자산', 'ticker': t, 'tags': '[자산]'}, body, '\n'.join(auto))
    for name, th in S.THEMES.items():
        exposed = [t for t, a in S.ASSETS.items() if name in a['exposure'] and t in holdings]
        hist = [h for h, v in S.HISTORY.items() if name in v['links']]
        auto = [f"- 내 보유 중 노출 자산: {' '.join(link(t) for t in exposed) or '없음'}"]
        body = f"# {name}\n\n{th['note']}\n\n관련 역사: " + ' '.join(link(h) for h in hist)
        write_note(VAULT / th['type'] / f'{name}.md', {'type': th['type'], 'tags': f"[{th['type']}]"}, body, '\n'.join(auto))
    for name, h in S.HISTORY.items():
        auto = [f"- 오늘 국면과 닮음: {'예 — ' + ', '.join(set(h['regime']) & set(flags)) if name in analogs else '아니오'}"]
        body = (f"# {name}\n\n{h['text']}\n\n국면: " + ', '.join(h['regime'] or ['-']) +
                '\n연결: ' + ' '.join(link(x) for x in h['links']))
        write_note(VAULT / '역사' / f'{name}.md', {'type': '역사', 'tags': '[역사]'}, body, '\n'.join(auto))
    regime_lines = [f'- {k}: {v}' for k, v in macro.items()]
    for k, rule in S.REGIME_RULES.items():
        regime_lines.append(f"- {'🔴' if k in flags else '⚪'} {k}: {rule}")
    write_note(VAULT / '지표' / '거시 국면.md', {'type': '지표', 'tags': '[지표]'},
               '# 거시 국면\n\n국면 판단은 매매 규칙이 아니라 상황 설명용입니다.', '\n'.join(regime_lines))
    write_note(VAULT / '전략' / f"{strat['label']}.md", {'type': '전략', 'tags': '[전략]'},
               f"# {strat['label']}\n\n구성: " + ', '.join(f'{link(k)} {v:.0%}' for k, v in strat['weights'].items()) +
               '\n규칙: 200일선 ±3% 밴드 · 변동성 상한 · 청산 시 방어자산(금·채권·원자재·현금 중 모멘텀 1위) · 월말 리밸런싱',
               '\n'.join(f'- {link(t)} {w:.1%}' for t, w in sorted(total.items(), key=lambda kv: -kv[1])))


def briefing(day, strat, sleeves, total, defensive, macro, flags, analogs, rebalance, changes):
    L = [f'[투자 온톨로지 브리핑] {day.date()} · {strat["label"]}', '']
    L.append('■ 매매 신호 (200일선 ±3% 밴드)')
    for a, s in sleeves.items():
        L.append(f"- {a}: {'보유' if s['on'] else '청산'} | {s['base']} 200일선 대비 {s['gap']:+.1%} | 변동성 {s['vol']:.0%}")
    L.append(f'- 방어자산: {defensive}')
    L.append('■ 목표 비중: ' + ' · '.join(f'{t} {w:.0%}' for t, w in sorted(total.items(), key=lambda kv: -kv[1])))
    L.append('')
    L.append('■ 거시 국면: ' + (', '.join(flags) if flags else '경고 없음'))
    for k, v in macro.items():
        L.append(f'- {k}: {v}')
    if analogs:
        L.append('■ 닮은 역사: ' + ', '.join(analogs))
    L.append('')
    L.append('■ 오늘 할 일')
    L += changes or []
    if rebalance: L.append('- 월말: 전체를 목표 비중으로 리밸런싱')
    if not changes and not rebalance: L.append('- 변경 없음 (규칙대로 유지)')
    L.append('')
    L.append('※ 국면·역사는 이해를 돕는 정보입니다. 매매는 규칙대로.')
    return '\n'.join(L)


def event_notes(events, holdings):
    """이슈 테마 노트: 관심도·헤드라인을 기록하고 국가·원자재·역사·내 보유 자산과 연결."""
    import events as EV
    exposure = {}
    for name, e in events.items():
        e['level'] = EV.level(e['ratio'])
        held = [t for t in holdings if t in S.ASSETS and set(S.ASSETS[t]['exposure']) & set(e['links'])]
        for t in held:
            exposure.setdefault(t, []).append({'name': name, 'level': e['level']})
        auto = [f"- 관심도: {e['level']}" + (f" ({e['ratio']:.2f}배, 최근 7일 / 이전 90일)" if e['ratio'] else ''),
                f"- 내 보유 중 노출: {' '.join(link(t) for t in held) or '없음'}", '- 최근 헤드라인:']
        auto += [f"  - [{h['title']}]({h['url']}) · {h['domain']}" for h in e['headlines']] or ['  - 없음']
        body = (f'# {name}\n\n검색식: `{e["query"]}`\n\n연결: ' + ' '.join(link(x) for x in e['links']) +
                ('\n관련 역사: ' + ' '.join(link(h) for h in e['history']) if e['history'] else ''))
        write_note(VAULT / '이슈' / f'{name}.md', {'type': '이슈', 'tags': '[이슈]'}, body, '\n'.join(auto))
    for t in holdings:
        exposure.setdefault(t, [])
    return exposure


def record_events(day, events):
    """data/events_history.csv에 테마별 관심도를 날짜별로 누적. 급증(1.5배 이상)이면 사건 노트 생성."""
    path = ROOT / 'data' / 'events_history.csv'
    path.parent.mkdir(exist_ok=True)
    hist = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=['date', 'theme', 'ratio'])
    today = str(day.date())
    rows = [{'date': today, 'theme': n, 'ratio': round(e['ratio'], 3)} for n, e in events.items() if e['ratio']]
    if rows:
        hist = pd.concat([hist[hist['date'] != today], pd.DataFrame(rows)], ignore_index=True)
        hist.to_csv(path, index=False)
    new_events = []
    for n, e in events.items():
        if e['ratio'] and e['ratio'] >= 1.5:
            eid = f'{today} {n} 급증'
            new_events.append({'id': eid, 'date': today, 'theme': n, 'ratio': round(e['ratio'], 2),
                               'headlines': [h['title'] for h in e['headlines'][:3]]})
            lines = [f"- 관심도: {e['ratio']:.2f}배 (최근 7일 / 이전 90일)", '- 헤드라인:']
            lines += [f"  - [{h['title']}]({h['url']}) · {h['domain']}" for h in e['headlines']] or ['  - 없음']
            body = (f'# {eid}\n\n이슈: {link(n)}\n영향: ' + ' '.join(link(x) for x in e['links']) +
                    ('\n유사 역사: ' + ' '.join(link(h) for h in e['history']) if e['history'] else '') +
                    '\n\n## 메모\n(이 사건에 대한 생각을 자유롭게 적으세요. 자동 갱신되지 않습니다.)')
            write_note(VAULT / '사건' / f'{eid}.md', {'type': '사건', 'date': today, 'tags': '[사건]'}, body, '\n'.join(lines))
    # 대시보드용: 테마별 최근 기록
    series = {}
    for n, g in hist.groupby('theme'):
        g = g.sort_values('date').tail(60)
        series[n] = {'d': g['date'].tolist(), 'v': g['ratio'].astype(float).round(3).tolist()}
    return new_events, series


def org_notes():
    for name, o in S.ORGS.items():
        rel = '\n'.join(f"- {k}: " + ' '.join(link(x) for x in v) for k, v in o['rel'].items())
        write_note(VAULT / o['type'] / f'{name}.md', {'type': o['type'], 'tags': f"[{o['type']}]"},
                   f"# {name}\n\n{o['note']}\n\n## 관계\n{rel}", '- (정적 노드: 관계는 seeds.py에서 관리)')


def macro_series(fred):
    idx = pd.date_range(end=pd.Timestamp.today(), periods=120, freq='ME')
    def mon(s):
        return s.resample('ME').last().reindex(idx) if s is not None else pd.Series(index=idx, dtype=float)
    cpi = fred.get('CPIAUCSL'); cpi_yoy = (cpi / cpi.shift(12) - 1) * 100 if cpi is not None else None
    r = lambda s: [None if pd.isna(v) else round(float(v), 2) for v in mon(s)]
    return {'d': [f'{d:%Y-%m}' for d in idx], 'cpi': r(cpi_yoy), 'unrate': r(fred.get('UNRATE')), 'curve': r(fred.get('T10Y2Y'))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='텔레그램 전송 안 함')
    ap.add_argument('--no-events', action='store_true', help='GDELT 수집 생략(빠른 테스트)')
    args = ap.parse_args()
    import json
    import dashboard
    import events as EV
    strat = C.STRATEGIES[C.ACTIVE_STRATEGY]
    px = load_prices()
    day, sleeves, total, defensive = strategy_targets(px, strat)
    fred = load_fred()
    macro, flags, analogs = macro_state(fred)
    events = {} if args.no_events else EV.collect()
    # 국면 기반 + 급증 이슈 기반 역사 연결
    why = {a: '거시 국면 ' + ', '.join(set(S.HISTORY[a]['regime']) & set(flags)) for a in analogs}
    for name, e in events.items():
        if e['ratio'] and e['ratio'] >= 1.5:
            for h in e['history']:
                why[h] = (why[h] + ' · ' if h in why else '') + f'이슈 급증: {name}'
    analogs = list(why)
    # 전날과 비교해 바뀐 슬리브 찾기
    state_file = VAULT / '.state.json'
    prev = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
    if prev.get('date') == str(day.date()): prev = prev.get('previous', {})
    changes = [f"- {a} 슬리브: {prev['sleeves'][a]} → {s['hold']}" for a, s in sleeves.items()
               if prev.get('sleeves', {}).get(a) not in (None, s['hold'])]
    rebalance = is_month_end(day)
    build_vault(px, day, strat, sleeves, total, defensive, macro, flags, analogs)
    holdings = [t for t, w in total.items() if w > 0.001]
    exposure = event_notes(events, holdings) if events else {t: [] for t in holdings}
    text = briefing(day, strat, sleeves, total, defensive, macro, flags, analogs, rebalance, changes)
    hot = [f"{n}({e['ratio']:.1f}배)" for n, e in sorted(events.items(), key=lambda kv: -(kv[1]['ratio'] or 0))
           if e['ratio'] and e['ratio'] >= 1.15]
    if hot:
        text = text.replace('\n■ 오늘 할 일', '\n■ 관심 급증 이슈: ' + ', '.join(hot) + '\n\n■ 오늘 할 일')
    # 대시보드
    charts = {}
    for s in sleeves.values():
        b = s['base']; p = px[b]; sma = p.rolling(C.SMA_DAYS).mean()
        tail = slice(-260, None)
        charts[b] = {'d': [f'{d:%Y-%m-%d}' for d in p.index[tail]], 'p': [round(float(v), 2) for v in p.iloc[tail]],
                     's': [None if pd.isna(v) else round(float(v), 2) for v in sma.iloc[tail]]}
    actions = [c.lstrip('- ') for c in changes] + (['월말: 전체를 목표 비중으로 리밸런싱'] if rebalance else [])
    # 이슈 관심도 기록 누적 + 급증 사건 노트 생성 (온톨로지가 날마다 자람)
    new_events, ev_hist = record_events(day, events)
    org_notes()
    asset_state = {}
    for t in S.ASSETS:
        if t in px:
            p = px[t]; sma = p.rolling(C.SMA_DAYS).mean()
            asset_state[t] = {'종가': round(float(p.iloc[-1]), 2), '200일선대비': f'{p.iloc[-1] / sma.iloc[-1] - 1:+.1%}',
                              '1개월': f'{p.iloc[-1] / p.iloc[-22] - 1:+.1%}'}
            if t in sleeves:
                asset_state[t]['신호'] = '보유' if sleeves[t]['on'] else '청산'
    # 하이브리드 역사: 금융 데이터(주 1회 갱신) × 시대 연표
    import history_link as HL
    hist_csv = ROOT / 'data' / 'history_monthly.csv'
    # 파일 수정 시각은 클라우드에서 매번 바뀌므로, 데이터의 마지막 달로 판단 (지난달까지 없으면 갱신)
    stale = True
    if hist_csv.exists():
        last = pd.read_csv(hist_csv, usecols=['month'])['month'].iloc[-1]
        stale = pd.Period(last, 'M') < pd.Timestamp.today().to_period('M') - 1
    if stale:
        try:
            import history_data
            history_data.build()
            print('역사 데이터 갱신 완료')
        except Exception as e:
            print(f'역사 데이터 갱신 실패(기존 파일 사용): {e}')
    chronicle, tl = [], None
    if hist_csv.exists():
        h, ev = HL.load()
        chronicle = HL.event_rows(h, ev)
        HL.write_notes(write_note, link, VAULT, chronicle)
        tl = HL.timeline(h, chronicle)
    import graph as G
    ontology = G.build(strat, total, sleeves, asset_state, events, flags, why, new_events, chronicle)
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs' / 'ontology.json').write_text(json.dumps(ontology, ensure_ascii=False, indent=1), encoding='utf-8')
    dashboard.write(ROOT / 'docs' / 'index.html', {
        'graph': ontology, 'event_history': ev_hist, 'timeline': tl,
        'date': str(day.date()), 'generated': pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y-%m-%d %H:%M KST'),
        'strategy': strat['label'], 'actions': actions or ['변경 없음 (규칙대로 유지)'],
        'targets': {t: round(w, 4) for t, w in total.items() if w > 0.001},
        'sleeves': sleeves, 'charts': charts, 'macro': macro, 'flags': flags, 'regime_rules': S.REGIME_RULES,
        'macro_series': macro_series(fred),
        'events': {n: {k: e[k] for k in ('ratio', 'level', 'links', 'history', 'headlines')} for n, e in events.items()},
        'exposure': exposure,
        'analogs': [{'name': a, 'why': why[a], 'text': S.HISTORY[a]['text']} for a in analogs if a in S.HISTORY],
    })
    links = ' '.join(link(x) for x in [*sleeves, defensive, '거시 국면', strat['label'], *analogs, *events])
    note = VAULT / '브리핑' / f'{day.date()}.md'
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f'---\ntype: 브리핑\ndate: {day.date()}\ntags: [브리핑]\n---\n```\n{text}\n```\n\n연결: {links}\n', encoding='utf-8')
    state_file.write_text(json.dumps({'date': str(day.date()), 'sleeves': {a: s['hold'] for a, s in sleeves.items()},
                                      'previous': {k: v for k, v in prev.items() if k != 'previous'}},
                                     ensure_ascii=False), encoding='utf-8')
    print(text)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
