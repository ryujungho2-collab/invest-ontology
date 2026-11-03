"""
이슈 레이더
- 관심도: 위키백과 조회수 API (Wikimedia REST, 무료·키 불필요)
    테마별 관련 문서 조회수 합계의 '최근 7일 평균 / 이전 90일 평균'
- 헤드라인: 구글 뉴스 RSS (무료·키 불필요), 최근 3일
GDELT는 요청 제한이 심해 매일 자동 실행용으로는 쓰지 않음.
"""
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

UA = {'User-Agent': 'invest-ontology/1.0 (github.com/ryujungho2-collab/invest-ontology)'}
WIKI = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{}/daily/{}/{}'
NEWS = 'https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'

# 테마: 위키 문서들, 뉴스 검색식, 온톨로지 연결 대상, 연결 역사 국면
THEMES = {
    '무역·관세': (['Tariff', 'Trade_war', 'Protectionism'], 'tariffs OR "trade war" OR "export controls"', ['미국', '중국', '반도체', '달러'], ['1930 스무트-홀리 관세']),
    '분쟁·전쟁': (['War', 'Ceasefire', 'Airstrike'], 'war OR invasion OR missile strike', ['중동', '러시아', '원유', '금'], ['1990 걸프전', '1973 1차 오일쇼크']),
    '중동·에너지': (['OPEC', 'Strait_of_Hormuz', 'Price_of_oil'], 'OPEC OR "oil supply" OR "Strait of Hormuz"', ['원유', '중동'], ['1973 1차 오일쇼크', '1979 2차 오일쇼크와 볼커']),
    '중앙은행·금리': (['Federal_Reserve', 'Federal_funds_rate', 'Quantitative_easing'], '"Federal Reserve" OR "rate cut" OR "rate hike"', ['금리', '달러', '미국'], ['1979 2차 오일쇼크와 볼커', '2022 인플레이션 긴축']),
    '인플레이션': (['Inflation', 'Stagflation', 'Consumer_price_index'], 'inflation OR "consumer prices"', ['금리', '금', '원유'], ['1973 1차 오일쇼크', '2022 인플레이션 긴축']),
    'AI·기술': (['Artificial_intelligence', 'Large_language_model', 'Data_center'], '"artificial intelligence" OR "AI chips" OR "data center"', ['빅테크', '반도체', '구리'], ['1995 인터넷 붐', '2000 닷컴 붕괴']),
    '반도체 공급망': (['Semiconductor', 'TSMC', 'Nvidia'], 'semiconductor OR chipmaker OR TSMC', ['반도체', '대만', '한국'], []),
    '대만·중국 긴장': (['Taiwan_Strait', 'Political_status_of_Taiwan', 'South_China_Sea'], '"Taiwan Strait" OR "China military" OR "South China Sea"', ['대만', '중국', '반도체'], []),
    '금융 불안': (['Bank_run', 'Recession', 'Credit_crunch'], '"bank failure" OR "credit crunch" OR "debt crisis"', ['금리', '미국', '금'], ['2008 글로벌 금융위기']),
    '선거·정치': (['Impeachment', 'Government_shutdowns_in_the_United_States', 'Snap_election'], 'election OR "government shutdown" OR impeachment', ['미국', '한국'], []),
    '보건·팬데믹': (['Pandemic', 'Epidemic', 'Avian_influenza'], 'pandemic OR outbreak OR epidemic', ['미국', '원유'], ['2020 코로나 폭락']),
    '기후·재해': (['Hurricane', 'Earthquake', 'Wildfire'], 'hurricane OR earthquake OR drought OR wildfire', ['원유', '구리'], []),
    '에너지 전환·전력': (['Nuclear_power', 'Renewable_energy', 'Electrical_grid'], '"power grid" OR "electricity demand" OR "nuclear power"', ['구리', '빅테크'], []),
    '제재·탈달러': (['De-dollarization', 'International_sanctions', 'Gold_reserve'], 'sanctions OR "de-dollarization" OR "central bank gold"', ['러시아', '금', '달러'], ['1971 닉슨 쇼크']),
    # --- 지정학 ---
    '러시아·우크라이나': (['Russian_invasion_of_Ukraine', 'NATO', 'Ukraine'], 'Ukraine Russia war OR NATO', ['러시아', '유럽', '원유', '식량'], ['2022 인플레이션 긴축']),
    '한반도·북한': (['North_Korea', 'Kim_Jong_Un', 'Korean_Demilitarized_Zone'], '"North Korea" missile OR "Korean peninsula"', ['북한', '한국'], []),
    # --- 통화·금융 ---
    '달러·환율': (['United_States_dollar', 'Exchange_rate', 'South_Korean_won'], '"dollar index" OR "currency markets" OR "won dollar"', ['달러', '한국'], ['1985 플라자 합의']),
    '일본·엔캐리': (['Bank_of_Japan', 'Carry_(investment)', 'Japanese_yen'], '"Bank of Japan" OR "yen carry trade"', ['일본', '금리', '달러'], ['1990 일본 버블 붕괴']),
    '미국 부채·재정': (['National_debt_of_the_United_States', 'United_States_Treasury_security', 'Bond_vigilante'], '"US debt" OR "Treasury yields" OR "fiscal deficit"', ['미국', '금리', '금', '달러'], ['1971 닉슨 쇼크']),
    '부동산': (['Real_estate_bubble', 'Mortgage_loan', 'Commercial_real_estate'], '"housing market" OR "commercial real estate" OR mortgage rates', ['금리', '미국', '중국'], ['2008 글로벌 금융위기', '1990 일본 버블 붕괴']),
    '암호화폐': (['Bitcoin', 'Cryptocurrency', 'Stablecoin'], 'bitcoin OR crypto OR stablecoin', ['암호화폐', '달러'], []),
    '중국 경제': (['Economy_of_China', 'Renminbi', 'People\'s_Bank_of_China'], '"China economy" OR "Chinese stimulus" OR yuan', ['중국', '구리', '원유'], ['1990 일본 버블 붕괴']),
    # --- 원자재 ---
    '핵심 광물': (['Rare-earth_element', 'Lithium', 'Copper'], '"rare earths" OR lithium OR "copper prices"', ['구리', '중국'], []),
    '식량·농산물': (['Food_security', 'Fertilizer', 'Wheat'], '"food prices" OR wheat OR fertilizer', ['식량', '러시아'], []),
    # --- 산업·기술 ---
    '전기차·배터리': (['Electric_vehicle', 'Lithium-ion_battery', 'Tesla,_Inc.'], '"electric vehicle" OR "EV battery"', ['구리', '중국', '한국'], []),
    '바이오·비만치료제': (['Semaglutide', 'Tirzepatide', 'Biotechnology'], 'GLP-1 OR obesity drug OR biotech', ['헬스케어', '미국'], []),
    '양자·로봇': (['Quantum_computing', 'Humanoid_robot', 'Robotics'], '"quantum computing" OR "humanoid robot"', ['빅테크', '반도체'], ['1995 인터넷 붐']),
    '사이버보안': (['Cyberattack', 'Ransomware', 'Computer_security'], 'cyberattack OR ransomware OR hack', ['빅테크', '미국'], []),
    '방산': (['Arms_industry', 'Military_budget', 'Drone_warfare'], '"defense spending" OR "defense stocks" OR drones military', ['방산', '미국', '유럽'], []),
    # --- 사회·규제 ---
    '고용·노동': (['Unemployment', 'Layoff', 'Strike_action'], 'layoffs OR "jobs report" OR strike workers', ['미국', '금리'], []),
    '빅테크 규제': (['Antitrust', 'Digital_Markets_Act', 'Regulation_of_artificial_intelligence'], 'antitrust big tech OR "AI regulation"', ['빅테크', '미국', '유럽'], []),
    '인구·고령화': (['Population_ageing', 'Total_fertility_rate', 'Demographic_crisis'], '"birth rate" OR "aging population"', ['한국', '일본', '중국'], ['1990 일본 버블 붕괴']),
}


def wiki_views(article, days=120):
    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=days)
    url = WIKI.format(urllib.parse.quote(article, safe=''), start.strftime('%Y%m%d'), end.strftime('%Y%m%d'))
    for attempt in range(4):
        try:
            time.sleep(0.4)
            r = requests.get(url, headers=UA, timeout=20)
            if r.status_code == 429:                 # 요청 제한 → 잠시 쉬고 재시도
                time.sleep(3 * (attempt + 1))
                continue
            if not r.ok:                             # 404 등: 문서 제목 없음
                return None
            items = r.json().get('items', [])
            return pd.Series([i['views'] for i in items], index=pd.to_datetime([i['timestamp'][:8] for i in items]))
        except Exception:
            time.sleep(2)
    return None


def news_headlines(query, n=5):
    try:
        r = requests.get(NEWS.format(urllib.parse.quote(f'{query} when:3d')), headers=UA, timeout=20)
        root = ET.fromstring(r.content)
        out = []
        for it in root.iter('item'):
            src = it.find('source')
            out.append({'title': it.findtext('title', ''), 'url': it.findtext('link', ''),
                        'domain': src.text if src is not None else '', 'date': it.findtext('pubDate', '')[:16]})
            if len(out) >= n:
                break
        return out
    except Exception as e:
        print(f'  뉴스 실패: {e}')
        return []


def collect():
    out = {}
    for name, (articles, query, links, history) in THEMES.items():
        item = {'query': query, 'articles': articles, 'links': links, 'history': history,
                'ratio': None, 'series': [], 'headlines': []}
        series = [s for s in (wiki_views(a) for a in articles) if s is not None and len(s) > 30]
        if series:
            s = pd.concat(series, axis=1).sum(axis=1).sort_index()
            recent, base = s.iloc[-7:].mean(), s.iloc[:-7].iloc[-90:].mean()
            item['ratio'] = float(recent / base) if base > 0 else None
            item['series'] = [{'d': str(k.date()), 'v': int(v)} for k, v in s.iloc[-90:].items()]
        item['headlines'] = news_headlines(query)
        time.sleep(1)
        out[name] = item
        r = item['ratio']
        print(f"  이슈 [{name}] 관심도 {'-' if r is None else round(r, 2)} · 문서 {len(series)}/{len(articles)} · 헤드라인 {len(item['headlines'])}")
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
