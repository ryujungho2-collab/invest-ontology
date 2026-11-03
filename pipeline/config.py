"""전략·지표 설정. ACTIVE_STRATEGY만 바꾸면 전략이 바뀝니다."""

STRATEGIES = {
    # 발표용 전략 (2017–2026 기준 최적화, 금 비중이 큼)
    'presentation': {
        'label': '금 쿠션 레버리지 추세 (발표안)',
        'weights': {'GLD': 0.45, 'TQQQ': 0.35, 'SOXL': 0.10, 'TECL': 0.10},
        'trend': {'TQQQ': ('QQQ', 0.40), 'SOXL': ('SMH', 0.60), 'TECL': ('XLK', 0.50)},
    },
    # 앞으로 10년용 후보 D (2007–2016으로 설계, 2017–2026으로 검증 / 금 10%)
    'future_d': {
        'label': '광역 지수 레버리지 추세 (D안, 금 10%)',
        'weights': {'GLD': 0.10, 'TQQQ': 0.30, 'UPRO': 0.30, 'IEF': 0.30},
        'trend': {'TQQQ': ('QQQ', 0.40), 'UPRO': ('SPY', 0.40)},
    },
}
ACTIVE_STRATEGY = 'future_d'

SMA_DAYS, BAND, VOL_DAYS = 200, 0.03, 20
DEFENSIVE = ['GLD', 'IEF', 'TLT', 'DBC', 'CASH']   # CASH = BIL
CASH_TICKER = 'BIL'

# FRED 시리즈 (API 키 불필요한 CSV 엔드포인트 사용)
FRED = {
    'UNRATE': '실업률',
    'CPIAUCSL': '소비자물가지수',
    'T10Y2Y': '장단기 금리차(10년-2년)',
    'BAA10Y': '신용 스프레드(BAA-10년)',
    'DCOILWTICO': 'WTI 유가',
    'DTWEXBGS': '달러 지수(광의)',
}
