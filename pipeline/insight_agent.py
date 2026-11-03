"""
통찰 에이전트 (하네스 구조)
- 도구: 온톨로지·역사·예측 데이터를 탐색하는 함수들 (@beta_tool)
- 루프: Claude가 도구를 골라 쓰며 가설을 세우고 데이터로 검증 (SDK tool runner)
- 기록: 모든 도구 호출과 결과 요약을 이벤트 스트림(trace)으로 저장
- 사람 승인: 에이전트가 낸 가설은 옵시디언 '통찰/가설 검토.md'에서 체크해야 채택되고,
           채택된 가설은 다음 실행 때 에이전트가 다시 검증한다.
실행: ANTHROPIC_API_KEY 필요.  python pipeline/insight_agent.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'insights'
HYP = DATA / 'hypotheses.json'
VAULT = ROOT / 'vault'
MODEL = 'claude-opus-5-5'
TRACE = []


def _log(tool, args, result):
    s = json.dumps(result, ensure_ascii=False, default=str)
    TRACE.append({'t': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'type': 'tool',
                  'tool': tool, 'input': args, 'output_preview': s[:300], 'output_chars': len(s)})
    return s


def _ctx():
    return json.loads((DATA / 'context.json').read_text(encoding='utf-8'))


def _graph():
    return json.loads((ROOT / 'docs' / 'ontology.json').read_text(encoding='utf-8'))


# ------------------------------------------------------------------ 도구 정의
def make_tools():
    from anthropic import beta_tool

    @beta_tool
    def get_today_state() -> str:
        """오늘의 전체 상황: 전략 신호, 목표 비중, 거시 지표와 국면 경고, 이슈 관심도(최근 7일/이전 90일)와 헤드라인,
        장기 기대수익(채점 통과)과 단기 유사국면 요약(채점 탈락). 분석을 시작할 때 가장 먼저 호출하세요."""
        c = _ctx()
        issues = sorted(c['issues'].items(), key=lambda kv: -(kv[1]['ratio'] or 0))
        f = c.get('forecast') or {}
        out = {'date': c['date'], 'strategy': c['strategy'], 'targets': c['targets'],
               'signals': {k: {'on': v['on'], 'base': v['base'], 'gap_vs_200d': round(v['gap'], 4), 'vol': round(v['vol'], 3)} for k, v in c['sleeves'].items()},
               'macro': c['macro'], 'regime_flags': c['flags'],
               'issues_top': [{'theme': n, **e} for n, e in issues[:12]],
               'long_term_forecast': f.get('long', {}) and {k: f['long'][k] for k in ('expected', 'low', 'high', 'cape', 'hist_avg', 'skill')},
               'short_term_summary': (f.get('current') or {}).get('summary'), 'forecast_scores': f.get('scores')}
        return _log('get_today_state', {}, out)

    @beta_tool
    def find_analogs() -> str:
        """지금의 거시·시장 상태와 가장 닮은 과거 20개월과, 그 시기(±3개월)의 시대 사건, 이후 12개월 결과.
        주의: 이 유사국면 방식은 12개월 방향 예측에서 채점 탈락(기저율보다 못함)했으므로 '역사적 이야기'의 재료로만 쓰세요."""
        c = _ctx()
        return _log('find_analogs', {}, (c.get('forecast') or {}).get('current', {}).get('analogs', []))

    @beta_tool
    def query_chronicle(category: str = '', start_year: int = 1950, end_year: int = 2026, keyword: str = '') -> str:
        """1950년 이후 시대·금융 연표 검색. 사건마다 당시 시장 상태(물가, 금리차, 고점 대비 낙폭 등)와 이후 12개월 결과 포함.

        Args:
            category: 분류 필터 (전쟁·분쟁, 정치·외교, 기술, 보건, 재해, 에너지, 무역, 통화·금융정책, 금융위기, 사회). 비우면 전체.
            start_year: 시작 연도.
            end_year: 끝 연도.
            keyword: 제목·설명에 포함될 단어 (예: 관세, 오일, AI).
        """
        import history_link as HL
        h, ev = HL.load()
        rows = HL.event_rows(h, ev)
        out = [r for r in rows if (not category or r['category'] == category)
               and start_year <= int(r['month'][:4]) <= end_year
               and (not keyword or keyword in r['title'] or keyword in r['description'])]
        slim = [{k: r.get(k) for k in ('month', 'title', 'category', 'description', 'state', 'fwd')} for r in out[:25]]
        return _log('query_chronicle', {'category': category, 'start_year': start_year, 'end_year': end_year, 'keyword': keyword}, slim)

    @beta_tool
    def get_node(name: str) -> str:
        """온톨로지의 대상(자산·국가·산업·원자재·기관·기업·이슈·역사·연표 등) 하나의 속성과 들어오고 나가는 관계.

        Args:
            name: 노드 이름 (예: TQQQ, 대만, 원유, TSMC, 무역·관세, 1973 1차 오일쇼크).
        """
        g = _graph()
        node = next((n for n in g['nodes'] if n['id'] == name), None)
        if not node:
            cands = [n['id'] for n in g['nodes'] if name in n['id']][:10]
            return _log('get_node', {'name': name}, {'error': '없음', '비슷한 이름': cands})
        out = {'node': node, 'out': [(e['rel'], e['target']) for e in g['edges'] if e['source'] == name][:40],
               'in': [(e['rel'], e['source']) for e in g['edges'] if e['target'] == name][:40]}
        return _log('get_node', {'name': name}, out)

    @beta_tool
    def impact_paths() -> str:
        """관심도 상위 이슈가 온톨로지 관계를 따라 내 보유 자산까지 이어지는 경로(최대 4단계)."""
        return _log('impact_paths', {}, _ctx().get('paths', []))

    @beta_tool
    def compare_with_month(month: str) -> str:
        """특정 과거 달(YYYY-MM)의 시장 상태를 오늘과 나란히 비교하고, 그 달 이후 3·6·12개월에 실제로 일어난 일을 보여줌.

        Args:
            month: 비교할 과거 달, 예: 1973-10, 2007-10, 2018-07.
        """
        import forecast as F
        h = F.load()
        m = pd.Period(month, 'M')
        today = h[list(F.FEATURES)].dropna().index[-1]
        if m not in h.index:
            return _log('compare_with_month', {'month': month}, {'error': '데이터 없음'})
        cols = list(F.FEATURES)
        out = {'features': {F.FEATURES[c]: {'그때': round(float(h.at[m, c]), 2) if pd.notna(h.at[m, c]) else None,
                                            '오늘': round(float(h.at[today, c]), 2)} for c in cols},
               'after': {k: (None if pd.isna(h.at[m, k]) else round(float(h.at[m, k]), 1))
                         for k in ['fwd_sp_3', 'fwd_sp_6', 'fwd_sp_12', 'fwd_bond_12', 'fwd_gold_12', 'fwd_oil_12', 'fwd_sp_mdd_12']},
               'recession_then': bool(h.at[m, 'recession'] == 1)}
        return _log('compare_with_month', {'month': month}, out)

    @beta_tool
    def get_hypotheses() -> str:
        """사용자가 채택한 이전 가설 목록과 각 가설의 확인 기준·기한. 오늘 데이터로 각각이 맞아가는지 판정하세요."""
        hyps = json.loads(HYP.read_text(encoding='utf-8')) if HYP.exists() else []
        return _log('get_hypotheses', {}, [h for h in hyps if h.get('approved')])

    return [get_today_state, find_analogs, query_chronicle, get_node, impact_paths, compare_with_month, get_hypotheses]


SYSTEM = """당신은 개인 투자자의 '온톨로지 기반 통찰 분석가'입니다. 슈카월드처럼 금융 데이터와 실제 역사를 엮어 지금의 의미를 해석합니다.

원칙
- 데이터로 확인한 것만 근거로 쓰고, 근거마다 어떤 도구·노드·숫자에서 왔는지 밝힌다.
- 예측 채점표를 존중한다. 채점 탈락한 단기 유사국면은 '이야기의 재료'로만 쓰고 확률 예측처럼 말하지 않는다. 채점 통과한 장기 기대수익은 근거로 써도 된다.
- 하나의 이야기에 갇히지 않는다. 통찰마다 반대 시나리오를 함께 쓴다.
- 매매 지시는 하지 않는다. 사용자의 매매는 규칙(200일선 ±3% 밴드, 헤지 자산 교체)이 결정한다. 당신의 역할은 '무엇을 지켜봐야 하는지'를 알려주는 것이다.
- 사용자가 채택한 가설이 있으면 오늘 데이터로 각각 '진행중/확인됨/반박됨'을 판정한다.

작업 순서
1) get_today_state로 전체 상황을 본다. 2) 눈에 띄는 이슈·국면을 골라 get_node, impact_paths로 연결을 추적한다.
3) find_analogs, query_chronicle, compare_with_month로 역사적 유사점과 차이점을 확인한다. 4) get_hypotheses로 이전 가설을 점검한다.
5) 마지막 답변은 아래 JSON 하나만, 코드블록(```json) 안에 출력한다. 한국어로 쓴다.

{"headline": "오늘을 한 문장으로",
 "insights": [{"title": "...", "thesis": "핵심 주장 2~3문장", "evidence": ["근거(출처 도구·노드·숫자 명시)", ...],
               "history_parallel": "닮은 역사와 결정적 차이", "counter_view": "반대 시나리오", "watch": ["확인할 신호와 기준값", ...],
               "nodes": ["관련 온톨로지 노드 이름", ...], "confidence": "낮음|중간|높음", "horizon": "1개월|3개월|1년|10년"}],
 "portfolio_lens": "내 보유 자산 관점에서의 의미 (매매 지시 없이)",
 "hypotheses": [{"statement": "검증 가능한 가설", "check": "판정 기준(어떤 숫자가 어떻게 되면)", "by": "YYYY-MM-DD"}],
 "hypothesis_reviews": [{"id": "...", "status": "진행중|확인됨|반박됨", "note": "..."}],
 "blind_spots": ["데이터나 온톨로지에 없어 판단이 약한 부분"]}
통찰은 3~5개."""


def run(max_iterations=18):
    import anthropic
    TRACE.clear()
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL, max_tokens=32000, max_iterations=max_iterations,
        thinking={'type': 'adaptive', 'display': 'summarized'}, output_config={'effort': 'high'},
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',
        system=SYSTEM, tools=make_tools(),
        messages=[{'role': 'user', 'content': '오늘의 통찰 보고서를 작성해 주세요.'}])
    final, usage = None, {'input': 0, 'output': 0}
    for msg in runner:
        final = msg
        usage['input'] += msg.usage.input_tokens
        usage['output'] += msg.usage.output_tokens
        for b in msg.content:
            if b.type == 'thinking' and getattr(b, 'thinking', ''):
                TRACE.append({'type': 'thinking', 'text': b.thinking[:600]})
            elif b.type == 'text' and b.text.strip():
                TRACE.append({'type': 'text', 'text': b.text[:600]})
            elif b.type == 'tool_use':
                TRACE.append({'type': 'call', 'tool': b.name, 'input': b.input})
    if final is None or final.stop_reason == 'refusal':
        raise RuntimeError(f'에이전트 응답 없음/거절: {getattr(final, "stop_reason", None)}')
    text = ''.join(b.text for b in final.content if b.type == 'text')
    m = re.search(r'```json\s*(\{.*\})\s*```', text, re.S) or re.search(r'(\{.*\})', text, re.S)
    report = json.loads(m.group(1)) if m else {'headline': '파싱 실패', 'raw': text}
    report['meta'] = {'author': f'통찰 에이전트 ({final.model})', 'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      'context_date': _ctx()['date'], 'tool_calls': sum(1 for t in TRACE if t['type'] == 'tool'), 'usage': usage}
    report['trace'] = TRACE[:]
    save(report)
    return report


def save(report):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    (OUT / f"{report['meta']['context_date']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    # 새 가설을 후보로 등록 (승인 전)
    hyps = json.loads(HYP.read_text(encoding='utf-8')) if HYP.exists() else []
    known = {h['statement'] for h in hyps}
    for i, h in enumerate(report.get('hypotheses', [])):
        if h['statement'] not in known:
            hyps.append({'id': f"H{report['meta']['context_date'].replace('-', '')}-{i + 1}", **h,
                         'created': report['meta']['context_date'], 'approved': False, 'status': '후보'})
    for r in report.get('hypothesis_reviews', []):
        for h in hyps:
            if h['id'] == r.get('id'):
                h['status'], h['note'] = r.get('status', h.get('status')), r.get('note', '')
    HYP.write_text(json.dumps(hyps, ensure_ascii=False, indent=1), encoding='utf-8')


def sync_approvals(vault=VAULT):
    """옵시디언 '통찰/가설 검토.md'의 체크박스(- [x] H...)를 읽어 채택 여부 반영."""
    note = vault / '통찰' / '가설 검토.md'
    if not (note.exists() and HYP.exists()):
        return
    checked = set(re.findall(r'- \[[xX]\] \*\*(H[\d-]+)\*\*', note.read_text(encoding='utf-8')))
    hyps = json.loads(HYP.read_text(encoding='utf-8'))
    for h in hyps:
        h['approved'] = h['id'] in checked
        if h['approved'] and h.get('status') == '후보':
            h['status'] = '진행중'
    HYP.write_text(json.dumps(hyps, ensure_ascii=False, indent=1), encoding='utf-8')


def write_vault(report, write_note, link, vault=VAULT):
    sync_approvals(vault)
    L = [f"**{report.get('headline', '')}**", '', f"작성: {report.get('meta', {}).get('author', '')} · 기준일 {report.get('meta', {}).get('context_date', '')}", '']
    for i, ins in enumerate(report.get('insights', []), 1):
        L += [f"### {i}. {ins.get('title', '')} ({ins.get('confidence', '')} · {ins.get('horizon', '')})", ins.get('thesis', ''), '', '근거:']
        L += [f'- {e}' for e in ins.get('evidence', [])]
        L += ['', f"역사: {ins.get('history_parallel', '')}", f"반대 시나리오: {ins.get('counter_view', '')}", '지켜볼 신호:']
        L += [f'- {w}' for w in ins.get('watch', [])]
        L += ['연결: ' + ' '.join(link(n) for n in ins.get('nodes', [])), '']
    L += ['### 내 포트폴리오 관점', report.get('portfolio_lens', ''), '', '### 사각지대'] + [f'- {b}' for b in report.get('blind_spots', [])]
    write_note(vault / '통찰' / '최신 통찰.md', {'type': '통찰', 'tags': '[통찰]'},
               '# 최신 통찰\n\n온톨로지를 탐색한 통찰 에이전트의 보고서. 매매 지시가 아니라 "무엇을 지켜볼지"에 대한 해석.', '\n'.join(L))
    hyps = json.loads(HYP.read_text(encoding='utf-8')) if HYP.exists() else []
    path = vault / '통찰' / '가설 검토.md'
    prev = path.read_text(encoding='utf-8') if path.exists() else ''
    checked = set(re.findall(r'- \[[xX]\] \*\*(H[\d-]+)\*\*', prev))
    lines = ['# 가설 검토', '', '에이전트가 낸 가설입니다. **채택하려면 체크박스를 체크**하세요. 채택된 가설은 다음 실행부터 에이전트가 맞는지 추적합니다.', '']
    for h in hyps:
        box = 'x' if h['id'] in checked else ' '
        lines.append(f"- [{box}] **{h['id']}** {h['statement']}  ")
        lines.append(f"  확인 기준: {h.get('check', '')} · 기한: {h.get('by', '')} · 상태: {h.get('status', '')}{(' · ' + h['note']) if h.get('note') else ''}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    r = run()
    print(r.get('headline'))
    print('도구 호출', r['meta']['tool_calls'], '토큰', r['meta']['usage'])
