# 투자 온톨로지 (GitHub Actions + 옵시디언)

매일 아침 7시(한국 시간), GitHub 클라우드가 자동으로:
1. 시장 가격을 받아 **전략 신호**(200일선 ±3% 밴드, 변동성 상한, 방어자산 교체)를 계산하고
2. 미국 연준(FRED)의 **거시 지표**로 국면(경기둔화·고물가·금리역전·신용경색)을 판단하고
3. 국면과 닮은 **역사 국면**(1973 오일쇼크, 2008 금융위기 등)을 연결하고
4. **옵시디언 노트**(자산·국가·산업·원자재·역사·지표·전략)를 갱신하고 그날의 **브리핑 노트**를 만들고
5. 같은 브리핑을 **텔레그램**으로 보냅니다.

PC가 꺼져 있어도 돌아갑니다. 비공개 저장소 무료 한도(월 2,000분) 안에서 하루 2~3분 정도 씁니다.

```
ontology/
├─ pipeline/
│  ├─ config.py   ← 전략 선택(ACTIVE_STRATEGY), 지표 목록
│  ├─ seeds.py    ← 온톨로지의 대상과 관계(자산 노출, 국가·산업 설명, 역사 국면)
│  └─ run.py      ← 매일 실행되는 본체
├─ vault/         ← 옵시디언이 보는 노트 (자동 생성·갱신)
├─ .github/workflows/daily.yml  ← 매일 실행 예약
└─ requirements.txt
```

---

## 1. GitHub에 올리기 (처음 한 번)
1. github.com 로그인 → 오른쪽 위 **+ → New repository**
2. 이름: `invest-ontology`, **Private** 선택 → Create
3. 이 `ontology` 폴더 안의 내용을 저장소에 올립니다. 쉬운 방법은 **GitHub Desktop**입니다.
   - GitHub Desktop 설치 → File → Add local repository → 이 `ontology` 폴더 선택
   - "create a repository" 안내가 나오면 만들기 → Publish repository (Private 체크 유지)
   - ⚠️ `.github` 폴더까지 올라가야 자동 실행이 됩니다. 웹 업로드는 숨김 폴더가 빠질 수 있어 GitHub Desktop을 권합니다.

## 2. 텔레그램 비밀값 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**
| 이름 | 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 받은 토큰 |
| `TELEGRAM_CHAT_ID` | `auto/get_chat_id.py`로 확인한 숫자 |

> 토큰은 저장소 파일이나 채팅에 쓰지 말고 이 Secrets에만 넣으세요.

## 3. 첫 실행
저장소 → **Actions** 탭 → (안내가 나오면 Enable) → `daily-ontology` → **Run workflow**
- 1~2분 뒤 텔레그램 메시지가 오고, `vault/브리핑/`에 오늘 노트가 커밋됩니다.
- 그다음부터는 평일 매일 오전 7시에 자동으로 돌아갑니다.

## 4. 옵시디언 연결
1. 옵시디언 설치 (obsidian.md)
2. GitHub Desktop으로 저장소를 내 PC에 Clone (이미 위에서 올린 폴더가 있으면 그 폴더 그대로)
3. 옵시디언 → **Open folder as vault** → 저장소 폴더(`invest-ontology`) 선택
4. 매일 자동 갱신을 받으려면: 설정 → 커뮤니티 플러그인 → **Obsidian Git** 설치 → "Pull on startup" 켜기
   (또는 아침에 GitHub Desktop에서 Fetch → Pull)
5. **그래프 뷰** (왼쪽 사이드바 또는 Ctrl+G)
   - 그룹 색: `tag:#자산`, `tag:#역사`, `tag:#국가`, `tag:#지표`, `tag:#브리핑` 별로 색을 지정하면 온톨로지 지도가 됩니다.

## 노트 고치기 규칙
- 각 노트의 `<!-- 자동 갱신 시작 -->` ~ `<!-- 자동 갱신 끝 -->` 사이만 매일 덮어씁니다.
- 그 밖의 부분(설명, 내 메모, 링크 추가)은 자유롭게 써도 지워지지 않습니다.
- 새 자산·국가·역사 국면을 추가하려면 `pipeline/seeds.py`에 한 줄 추가하면 다음 실행 때 노트가 생깁니다.

## 전략 바꾸기
`pipeline/config.py`의 `ACTIVE_STRATEGY`를 바꿉니다.
- `presentation`: 발표안 (금 45%, TQQQ·SOXL·TECL)
- `future_d`: 앞으로 10년용 후보 D안 (금 10%, TQQQ·UPRO·중기채)

## 원칙
국면 판단과 역사 연결은 **상황 이해용**입니다. 매매는 검증된 규칙대로만 합니다.

## 다음 단계 (예정)
- 국제 사건 자동 수집(GDELT) → 국가·원자재·내 보유 자산에 자동 연결
- 국면별 역사 시나리오 백테스트 결과를 역사 노트에 기록
