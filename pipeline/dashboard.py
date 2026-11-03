"""대시보드: docs/index.html 한 장으로 생성 (GitHub Pages로 공개). 차트는 Chart.js(MIT)."""
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>투자 온톨로지 대시보드</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f6f7f9;--card:#ffffff;--ink:#16202c;--sub:#5b6573;--line:#e3e6ea;--accent:#1f4e8c;--hot:#c2410c;--ok:#15803d;--warn:#b45309;--chip:#eef2f7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f141a;--card:#161d25;--ink:#e6ebf1;--sub:#9aa5b1;--line:#26303b;--accent:#7fb0ff;--hot:#fb923c;--ok:#4ade80;--warn:#fbbf24;--chip:#1e2731}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Noto Sans KR',system-ui,sans-serif;font-size:15px;line-height:1.55}
header{padding:28px 16px 8px;max-width:1200px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}header p{margin:0;color:var(--sub)}
main{max-width:1200px;margin:0 auto;padding:8px 16px 48px;display:grid;gap:16px;grid-template-columns:repeat(12,1fr)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;grid-column:span 12;min-width:0}
@media(min-width:900px){.s4{grid-column:span 4}.s6{grid-column:span 6}.s8{grid-column:span 8}}
h2{font-size:16px;margin:0 0 12px}h3{font-size:14px;margin:0 0 6px}.sub{color:var(--sub);font-size:13px}
.todo{font-size:17px;font-weight:700;color:var(--accent)}.todo li{margin:4px 0}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:var(--chip);border-radius:999px;padding:3px 10px;font-size:12px}
.flag{font-weight:700}.flag.on{color:var(--hot)}.flag.off{color:var(--sub);font-weight:400}
table{width:100%;border-collapse:collapse;font-size:13.5px}td,th{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--sub);font-weight:500}
.num{text-align:right;font-variant-numeric:tabular-nums}.lv{font-weight:700}.lv.급증{color:var(--hot)}.lv.증가{color:var(--warn)}.lv.감소{color:var(--sub)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.sig{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}.sigc{border:1px solid var(--line);border-radius:10px;padding:12px}
.state{font-weight:700}.state.on{color:var(--ok)}.state.off{color:var(--hot)}
.chart{position:relative;height:220px}.chart.sm{height:160px}
details{border-top:1px solid var(--line);padding:8px 0}summary{cursor:pointer;font-weight:500}details ul{margin:6px 0 0;padding-left:18px}
footer{max-width:1200px;margin:0 auto;padding:0 16px 32px;color:var(--sub);font-size:12px}
</style></head><body>
<header><h1>투자 온톨로지 대시보드</h1><p id="meta"></p></header>
<main>
 <section class="card s8"><h2>오늘 할 일</h2><ul class="todo" id="todo"></ul><p class="sub">국면·이슈·역사는 이해를 돕는 정보이며, 매매는 검증된 규칙대로만 합니다.</p></section>
 <section class="card s4"><h2>목표 비중</h2><div class="chart sm"><canvas id="wchart" aria-label="목표 비중 도넛 차트"></canvas></div><div id="wlist" class="chips" style="margin-top:10px"></div></section>
 <section class="card"><h2>매매 신호 · 200일선 ±3% 밴드</h2><div class="sig" id="sig"></div></section>
 <section class="card s6"><h2>거시 국면</h2><div id="flags" class="chips" style="margin-bottom:10px"></div><table id="macro"></table></section>
 <section class="card s6"><h2>거시 지표 추이 (10년)</h2><div class="chart"><canvas id="mchart" aria-label="물가·실업률·금리차 추이"></canvas></div></section>
 <section class="card s8"><h2>이슈 레이더 · 뉴스 관심도 (최근 7일 / 이전 90일)</h2><div class="chart"><canvas id="echart" aria-label="테마별 뉴스 관심도"></canvas></div><div id="heads"></div></section>
 <section class="card s4"><h2>내 보유 자산의 이슈 노출</h2><table id="expo"></table></section>
 <section class="card"><h2>닮은 역사 국면</h2><div id="hist"></div></section>
</main>
<footer>데이터: Yahoo Finance(가격), FRED(거시), GDELT(뉴스). 자동 생성 · 투자 권유 아님.</footer>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = (v,d=1) => (v>=0?'+':'')+(v*100).toFixed(d)+'%';
document.getElementById('meta').textContent = `${D.date} 종가 기준 · ${D.strategy} · 생성 ${D.generated}`;
document.getElementById('todo').innerHTML = D.actions.map(a=>`<li>${a}</li>`).join('');
const W = Object.entries(D.targets).sort((a,b)=>b[1]-a[1]);
const pal = ['#1f4e8c','#c2410c','#15803d','#7c3aed','#b45309','#0e7490','#be185d','#4b5563'];
new Chart(wchart,{type:'doughnut',data:{labels:W.map(x=>x[0]),datasets:[{data:W.map(x=>+(x[1]*100).toFixed(1)),backgroundColor:pal,borderWidth:0}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}}}});
wlist.innerHTML = W.map((x,i)=>`<span class="chip" style="border-left:6px solid ${pal[i%8]}">${x[0]} ${(x[1]*100).toFixed(1)}%</span>`).join('');
sig.innerHTML = Object.entries(D.sleeves).map(([a,s])=>`<div class="sigc"><h3>${a} <span class="state ${s.on?'on':'off'}">${s.on?'보유':'청산'}</span></h3>
 <div class="sub">${s.base} 200일선 대비 ${pct(s.gap)} · 변동성 ${(s.vol*100).toFixed(0)}% · 슬리브: ${Object.entries(s.hold).map(([t,w])=>t+' '+(w*100).toFixed(0)+'%').join(', ')}</div>
 <div class="chart sm"><canvas id="c_${a}" aria-label="${s.base} 가격과 200일선"></canvas></div></div>`).join('');
Object.entries(D.sleeves).forEach(([a,s])=>{const c=D.charts[s.base]; if(!c) return;
 new Chart(document.getElementById('c_'+a),{type:'line',data:{labels:c.d,datasets:[
  {label:s.base,data:c.p,borderColor:css('--accent'),borderWidth:1.6,pointRadius:0},
  {label:'200일선',data:c.s,borderColor:css('--sub'),borderWidth:1,pointRadius:0},
  {label:'+3%',data:c.s.map(v=>v&&v*1.03),borderColor:css('--ok'),borderDash:[4,4],borderWidth:1,pointRadius:0},
  {label:'-3%',data:c.s.map(v=>v&&v*0.97),borderColor:css('--hot'),borderDash:[4,4],borderWidth:1,pointRadius:0}]},
  options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:6}}}}});});
flags.innerHTML = Object.entries(D.regime_rules).map(([k,r])=>`<span class="chip flag ${D.flags.includes(k)?'on':'off'}" title="${r}">${D.flags.includes(k)?'●':'○'} ${k}</span>`).join('');
macro.innerHTML = Object.entries(D.macro).map(([k,v])=>`<tr><th>${k}</th><td>${v}</td></tr>`).join('');
const M=D.macro_series; new Chart(mchart,{type:'line',data:{labels:M.d,datasets:[
 {label:'물가상승률(%)',data:M.cpi,borderColor:css('--hot'),pointRadius:0,borderWidth:1.6},
 {label:'실업률(%)',data:M.unrate,borderColor:css('--accent'),pointRadius:0,borderWidth:1.6},
 {label:'장단기 금리차(%p)',data:M.curve,borderColor:css('--ok'),pointRadius:0,borderWidth:1.6}]},
 options:{maintainAspectRatio:false,scales:{x:{ticks:{maxTicksLimit:8}}}}});
const E = Object.entries(D.events).filter(e=>e[1].ratio!=null).sort((a,b)=>b[1].ratio-a[1].ratio);
new Chart(echart,{type:'bar',data:{labels:E.map(e=>e[0]),datasets:[{data:E.map(e=>+e[1].ratio.toFixed(2)),
 backgroundColor:E.map(e=>e[1].ratio>=1.5?css('--hot'):e[1].ratio>=1.15?css('--warn'):css('--sub'))}]},
 options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>'관심도 '+c.raw+'배'}}},scales:{x:{suggestedMin:0}}}});
heads.innerHTML = Object.entries(D.events).sort((a,b)=>(b[1].ratio||0)-(a[1].ratio||0)).map(([n,e])=>`<details><summary>${n} · <span class="lv ${e.level}">${e.level}</span> <span class="sub">${e.ratio?e.ratio.toFixed(2)+'배':''} · 연결: ${e.links.join(', ')}</span></summary>
 <ul>${e.headlines.map(h=>`<li><a href="${h.url}" target="_blank" rel="noopener">${h.title.replace(/</g,'&lt;')}</a> <span class="sub">${h.domain}</span></li>`).join('')||'<li class="sub">헤드라인 없음</li>'}</ul></details>`).join('');
expo.innerHTML = '<tr><th>보유 자산</th><th>연결된 이슈</th></tr>'+Object.entries(D.exposure).map(([t,xs])=>`<tr><td><b>${t}</b></td><td>${xs.map(x=>`<span class="lv ${x.level}">${x.name}</span>`).join(', ')||'<span class="sub">-</span>'}</td></tr>`).join('');
hist.innerHTML = (D.analogs.length?D.analogs:[]).map(h=>`<details open><summary>${h.name} <span class="sub">· 이유: ${h.why}</span></summary><p>${h.text}</p></details>`).join('')||'<p class="sub">현재 국면·이슈와 닮은 역사 국면 없음</p>';
</script></body></html>"""


def write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False)), encoding='utf-8')
