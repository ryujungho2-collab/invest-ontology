"""
금융 역사 데이터: 1950년 이후 월별 '시장 상태'와 '이후 수익률'.
출처
- S&P500 가격·배당·CAPE: Robert Shiller 데이터 (datahub.io/core/s-and-p-500), 1988년 이후 총수익은 Yahoo ^SP500TR
- 금: datahub.io/core/gold-prices (월별)
- 거시: FRED (CPIAUCSL, UNRATE, GS10, TB3MS, BAA, FEDFUNDS, WTISPLC, USREC)
- 나스닥 종합: Yahoo ^IXIC (1971~)
출력: data/history_monthly.csv  (매월 1행, 매일 실행 시 다시 만들 필요 없음 → 주 1회 정도 갱신)
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'history_monthly.csv'
START = '1950-01-01'
UA = {'User-Agent': 'invest-ontology/1.0'}


def _csv(url, tries=4):
    import time
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA if 'datahub' in url else None, timeout=(15, 90))
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text))
        except Exception as e:          # 일시적인 지연·차단 → 잠시 쉬고 재시도
            last = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f'다운로드 실패: {url} ({last})')


def fred(sid):
    df = _csv(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}')
    s = pd.to_numeric(df.iloc[:, 1], errors='coerce')
    s.index = pd.to_datetime(df.iloc[:, 0]).dt.to_period('M')
    return s.groupby(level=0).last()


def yahoo_monthly(ticker, start='1960-01-01'):
    px = yf.download(ticker, start=start, auto_adjust=True, progress=False)['Close']
    px = px.iloc[:, 0] if isinstance(px, pd.DataFrame) else px
    m = px.resample('ME').last()
    m.index = m.index.to_period('M')
    return m


def build():
    sp = _csv('https://datahub.io/core/s-and-p-500/r/data.csv')
    sp.index = pd.to_datetime(sp['Date']).dt.to_period('M')
    sp = sp.replace(0, np.nan)
    gold = _csv('https://datahub.io/core/gold-prices/r/monthly.csv')
    gold.index = pd.PeriodIndex(gold['Date'], freq='M')
    idx = pd.period_range(START, pd.Timestamp.today().to_period('M') - 1, freq='M')
    df = pd.DataFrame(index=idx)

    # S&P500 총수익지수: 1987년까지 실러(가격+배당/12), 1988년부터 ^SP500TR 월간 변화로 이어붙임
    price, div = sp['SP500'], sp['Dividend'].ffill()
    r_shiller = (price / price.shift(1) - 1) + div.shift(1) / price.shift(1) / 12
    tr = yahoo_monthly('^SP500TR', '1987-12-01').pct_change()
    r = r_shiller.reindex(idx)
    late = tr.reindex(idx).dropna()
    r.loc[late.index] = late
    df['sp_ret'] = r
    df['sp_tr'] = (1 + df['sp_ret'].fillna(0)).cumprod()
    df['sp_price'] = price.reindex(idx).combine_first(yahoo_monthly('^GSPC').reindex(idx))
    df['cape'] = sp['PE10'].reindex(idx)
    df['nasdaq'] = yahoo_monthly('^IXIC', '1971-01-01').reindex(idx)
    df['gold'] = pd.to_numeric(gold['Price'], errors='coerce').groupby(level=0).last().reindex(idx)
    for sid, col in [('CPIAUCSL', 'cpi'), ('UNRATE', 'unrate'), ('GS10', 'gs10'), ('TB3MS', 'tb3'),
                     ('BAA', 'baa'), ('FEDFUNDS', 'fedfunds'), ('WTISPLC', 'oil'), ('USREC', 'recession')]:
        df[col] = fred(sid).reindex(idx)

    # 상태 변수 (그 시점에 알 수 있는 값만)
    df['cpi_yoy'] = (df['cpi'] / df['cpi'].shift(12) - 1) * 100
    df['unrate_gap'] = df['unrate'] - df['unrate'].rolling(12, min_periods=9).mean()   # 발표 누락 달 허용
    df['curve'] = df['gs10'] - df['tb3']
    df['credit'] = df['baa'] - df['gs10']
    df['oil_yoy'] = (df['oil'] / df['oil'].shift(12) - 1) * 100
    df['gold_yoy'] = (df['gold'] / df['gold'].shift(12) - 1) * 100
    df['sp_trend'] = (df['sp_price'] / df['sp_price'].rolling(10).mean() - 1) * 100   # 10개월선 대비
    df['sp_mom12'] = (df['sp_tr'] / df['sp_tr'].shift(12) - 1) * 100
    df['sp_dd'] = (df['sp_tr'] / df['sp_tr'].cummax() - 1) * 100
    df['real_rate'] = df['gs10'] - df['cpi_yoy']

    # 10년 국채 근사 총수익: 이자 + 금리 변화 × 듀레이션(7)
    y = df['gs10'] / 100
    df['bond_ret'] = y.shift(1) / 12 - 7 * (y - y.shift(1))
    df['bond_tr'] = (1 + df['bond_ret'].fillna(0)).cumprod()

    # 이후 수익률 (예측 평가용 정답) — 미래 값이므로 상태 변수로 쓰면 안 됨
    for h in (3, 6, 12):
        df[f'fwd_sp_{h}'] = (df['sp_tr'].shift(-h) / df['sp_tr'] - 1) * 100
    df['fwd_nasdaq_12'] = (df['nasdaq'].shift(-12) / df['nasdaq'] - 1) * 100
    df['fwd_bond_12'] = (df['bond_tr'].shift(-12) / df['bond_tr'] - 1) * 100
    df['fwd_gold_12'] = (df['gold'].shift(-12) / df['gold'] - 1) * 100
    df['fwd_oil_12'] = (df['oil'].shift(-12) / df['oil'] - 1) * 100
    df['fwd_sp_mdd_12'] = [((df['sp_tr'].iloc[i:i + 13] / df['sp_tr'].iloc[i]).min() - 1) * 100
                           if i + 12 < len(df) else np.nan for i in range(len(df))]

    df.index.name = 'month'
    OUT.parent.mkdir(exist_ok=True)
    df.round(4).to_csv(OUT)
    return df


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    d = build()
    print(d.shape, d.index[0], '→', d.index[-1])
    print(d[['sp_tr', 'cpi_yoy', 'unrate_gap', 'curve', 'credit', 'oil_yoy', 'gold', 'nasdaq', 'fwd_sp_12']].describe().round(2).to_string())
    print(d.loc['1973-10':'1974-01', ['cpi_yoy', 'curve', 'oil_yoy', 'sp_dd', 'fwd_sp_12', 'recession']].round(1).to_string())
