"""
이슈 레이더: GDELT DOC 2.0 API (무료, 키 불필요)로 테마별 뉴스 관심도와 헤드라인 수집.
- 관심도: 최근 7일 평균 / 이전 90일 평균 (전 세계 뉴스 중 해당 테마 기사 비중 기준)
- GDELT 요청 제한: 5초에 1회 → 요청 사이 6초 대기
참고: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
import time
import urllib.parse

import pandas as pd
import requests

API = 'https://api.gdeltproject.org/api/v2/doc/doc'

# 테마: (검색식, 온톨로지 연결 대상, 연결 역사 국면)
THEMES = {
    '무역·관세': ('(tariff OR "trade war" OR "export controls")', ['미국', '중국', '반도체', '달러'], ['1930 스무트-홀리 관세']),
    '분쟁·전쟁': ('(war OR invasion OR missile OR airstrike)', ['중동', '러시아', '원유', '금'], ['1990 걸프전', '1973 1차 오일쇼크']),
    '중동·에너지': ('(OPEC OR "oil supply" OR "Strait of Hormuz")', ['원유', '중동'], ['1973 1차 오일쇼크', '1979 2차 오일쇼크와 볼커']),
    '중앙은행·금리': ('("Federal Reserve" OR "rate hike" OR "rate cut")', ['금리', '달러', '미국'], ['1979 2차 오일쇼크와 볼커', '2022 인플레이션 긴축']),
    '인플레이션': ('(inflation OR "consumer prices")', ['금리', '금', '원유'], ['1973 1차 오일쇼크', '2022 인플레이션 긴축']),
    'AI·기술': ('("artificial intelligence" OR "AI chips" OR "data center")', ['빅테크', '반도체', '구리'], ['1995 인터넷 붐', '2000 닷컴 붕괴']),
    '반도체 공급망': ('(semiconductor OR chipmaker OR TSMC)', ['반도체', '대만', '한국'], []),
    '대만·중국 긴장': ('("Taiwan Strait" OR "China military" OR "South China Sea")', ['대만', '중국', '반도체'], []),
    '금융 불안': ('("bank failure" OR "credit crunch" OR "debt crisis" OR "debt ceiling")', ['금리', '미국', '금'], ['2008 글로벌 금융위기']),
    '선거·정치': ('(election OR "government shutdown" OR impeachment)', ['미국', '한국'], []),
    '보건·팬데믹': ('(pandemic OR outbreak OR epidemic)', ['미국', '원유'], ['2020 코로나 폭락']),
    '기후·재해': ('(hurricane OR earthquake OR drought OR wildfire)', ['원유', '구리'], []),
    '에너지 전환·전력': ('("power grid" OR "electricity demand" OR "nuclear power" OR "renewable energy")', ['구리', '빅테크'], []),
    '제재·탈달러': ('(sanctions OR "de-dollarization" OR "central bank gold")', ['러시아', '금', '달러'], ['1971 닉슨 쇼크']),
}


def _get(params, tries=2):
    for i in range(tries):
        time.sleep(6)
        try:
            r = requests.get(API + '?' + urllib.parse.urlencode(params), timeout=30)
            if r.ok and r.text.lstrip().startswith('{'):
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(8)
    return None


def collect():
    out = {}
    for name, (query, links, history) in THEMES.items():
        item = {'query': query, 'links': links, 'history': history, 'ratio': None, 'series': [], 'headlines': []}
        tl = _get({'query': query, 'mode': 'timelinevol', 'timespan': '120d', 'format': 'json'})
        try:
            data = tl['timeline'][0]['data']
            s = pd.Series([d['value'] for d in data], index=pd.to_datetime([d['date'][:8] for d in data]))
            recent, base = s.iloc[-7:].mean(), s.iloc[:-7].iloc[-90:].mean()
            item['ratio'] = float(recent / base) if base > 0 else None
            w = s.resample('W').mean()
            item['series'] = [{'d': str(k.date()), 'v': round(float(v), 4)} for k, v in w.items()]
        except Exception as e:
            print(f'GDELT 관심도 실패 [{name}]: {e}')
        al = _get({'query': f'{query} sourcelang:english', 'mode': 'artlist', 'maxrecords': 5,
                   'timespan': '3d', 'sort': 'hybridrel', 'format': 'json'})
        try:
            item['headlines'] = [{'title': a['title'], 'url': a['url'], 'domain': a.get('domain', ''),
                                  'date': a.get('seendate', '')[:8]} for a in al.get('articles', [])][:5]
        except Exception as e:
            print(f'GDELT 헤드라인 실패 [{name}]: {e}')
        out[name] = item
        print(f"  이슈 [{name}] 관심도 {item['ratio'] if item['ratio'] is None else round(item['ratio'], 2)} · 헤드라인 {len(item['headlines'])}건")
    return out


def level(ratio):
    if ratio is None:
        return '데이터 없음'
    if ratio >= 1.5:
        return '급증'
    if ratio >= 1.15:
        return '증가'
    if ratio <= 0.8:
        return '감소'
    return '보통'
