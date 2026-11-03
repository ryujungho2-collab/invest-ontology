"""
온톨로지 그래프: 대상(node)과 종류가 있는 관계(edge)를 한곳에서 만든다.
대시보드 지도(docs/ontology.json)와 옵시디언 노트가 같은 그래프를 쓴다.

관계 종류
  노출   자산 → 국가/산업/원자재/요인      신호기준 자산 → 지수
  보유   전략 → 자산 (비중)               결정   기관 → 요인/원자재
  소재   기관·기업 → 국가/지역             산업   기업 → 산업
  공급   기업 → 기업                       영향   이슈 → 대상
  유사   이슈/국면 → 역사                  연관   역사 → 대상
  국면   역사 → 국면 조건                  발생   사건 → 이슈
"""
import seeds as S

TYPE_ORDER = ['전략', '자산', '국가', '지역', '산업', '원자재', '요인', '기관', '기업', '이슈', '사건', '국면', '역사', '연표']


def build(strat, total, sleeves, asset_state, events, flags, analogs_why, new_events, chronicle=()):
    nodes, edges = {}, []

    def node(i, t, **props):
        nodes.setdefault(i, {'id': i, 'type': t, 'props': {}})['props'].update(props)

    def edge(a, b, rel, **props):
        edges.append({'source': a, 'target': b, 'rel': rel, **props})

    node(strat['label'], '전략', 구성=', '.join(f'{k} {v:.0%}' for k, v in strat['weights'].items()))
    for t, a in S.ASSETS.items():
        node(t, '자산', 이름=a['name'], 목표비중=f"{total.get(t, 0):.1%}", 보유=total.get(t, 0) > 0.001,
             **asset_state.get(t, {}))
        for e in a['exposure']:
            edge(t, e, '노출')
        if a['signal_of']:
            edge(t, a['signal_of'], '신호기준')
    for t, w in total.items():
        if w > 0.001:
            edge(strat['label'], t, '보유', 비중=round(w, 4))
    for name, th in S.THEMES.items():
        node(name, th['type'], 설명=th['note'])
    for name, o in S.ORGS.items():
        node(name, o['type'], 설명=o['note'])
        for rel, targets in o['rel'].items():
            for x in targets:
                edge(name, x, rel)
    for k, rule in S.REGIME_RULES.items():
        node(k, '국면', 조건=rule, 켜짐=k in flags)
    for name, h in S.HISTORY.items():
        node(name, '역사', 설명=h['text'], 오늘과닮음=name in analogs_why, 이유=analogs_why.get(name, ''))
        for x in h['links']:
            edge(name, x, '연관')
        for r in h['regime']:
            edge(name, r, '국면')
    for name, e in events.items():
        node(name, '이슈', 관심도=e['ratio'], 수준=e['level'],
             헤드라인=[h['title'] for h in e['headlines'][:3]])
        for x in e['links']:
            edge(name, x, '영향')
        for h in e['history']:
            edge(name, h, '유사')
    for ev in new_events:
        node(ev['id'], '사건', 날짜=ev['date'], 관심도=ev['ratio'], 헤드라인=ev['headlines'])
        edge(ev['id'], ev['theme'], '발생')
    for r in chronicle:          # 시대·금융 연표 사건 (당시 상태와 이후 결과 포함)
        cid = f"{r['month']} {r['title']}"
        node(cid, '연표', 분류=r['category'], 설명=r['description'],
             **{f'당시 {k}': v for k, v in r.get('state', {}).items() if k in ('물가상승률', '장단기 금리차(10년-3개월)', 'S&P500 고점 대비')},
             **{f'이후12개월 {k}': v for k, v in r.get('fwd', {}).items() if k in ('S&P500', '금', '원유', '미국 10년 국채')})
        for x in r['links']:
            edge(cid, x, '배경')
    # 관계 대상 중 아직 노드가 없는 것(예: 지수 티커)은 기본 노드로
    for e in edges:
        for k in ('source', 'target'):
            if e[k] not in nodes:
                node(e[k], '요인')
    graph = {'nodes': list(nodes.values()), 'edges': edges, 'types': TYPE_ORDER}
    graph['paths'] = impact_paths(graph, events, [t for t, w in total.items() if w > 0.001])
    return graph


def impact_paths(graph, events, held, max_hops=4, per_theme=3, top_themes=8):
    """관심도 상위 이슈에서 출발해 관계를 따라 내 보유 자산까지 가는 최단 경로(최대 4단계).
    역사·국면·전략 노드는 경유하지 않는다(설명용 노드라 경로를 왜곡)."""
    skip_types = {'역사', '국면', '전략', '사건', '연표'}
    ntype = {n['id']: n['type'] for n in graph['nodes']}
    adj = {}
    for e in graph['edges']:
        if ntype.get(e['source']) in skip_types or ntype.get(e['target']) in skip_types:
            continue
        adj.setdefault(e['source'], []).append((e['target'], e['rel'], '→'))
        adj.setdefault(e['target'], []).append((e['source'], e['rel'], '←'))
    themes = sorted([n for n, e in events.items() if e['ratio']], key=lambda n: -events[n]['ratio'])[:top_themes]
    out = []
    for th in themes:
        found, seen, frontier = [], {th}, [[(th, None, None)]]
        for _ in range(max_hops):
            nxt = []
            for path in frontier:
                for nb, rel, d in adj.get(path[-1][0], []):
                    if nb in seen:
                        continue
                    # 다른 이슈·미보유 자산은 경유하지 않음 (경로가 돌아가는 것 방지)
                    if nb not in held and ntype.get(nb) in ('이슈', '자산'):
                        continue
                    np_ = path + [(nb, rel, d)]
                    if nb in held:
                        found.append(np_)
                    else:
                        nxt.append(np_)
                    seen.add(nb)
            frontier = nxt
            if len(found) >= per_theme:
                break
        for p in found[:per_theme]:
            out.append({'theme': th, 'ratio': events[th]['ratio'], 'level': events[th].get('level', ''),
                        'asset': p[-1][0], 'hops': len(p) - 1,
                        'text': p[0][0] + ''.join(f' —{rel}→ {n}' if d == '→' else f' ←{rel}— {n}' for n, rel, d in p[1:])})
    return out
