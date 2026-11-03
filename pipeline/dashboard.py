"""대시보드: docs/index.html 한 장 (GitHub Pages). 차트 Chart.js(MIT), 온톨로지 지도 Cytoscape.js(MIT)."""
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>투자 온톨로지</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#16202c;--sub:#5b6573;--line:#e2e5ea;--accent:#1f4e8c;--hot:#c2410c;--ok:#15803d;--warn:#b45309;--chip:#eef2f7;--sel:#e8f0fb}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f141a;--card:#161d25;--ink:#e6ebf1;--sub:#9aa5b1;--line:#26303b;--accent:#7fb0ff;--hot:#fb923c;--ok:#4ade80;--warn:#fbbf24;--chip:#1e2731;--sel:#1b2a3d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Noto Sans KR',system-ui,sans-serif;font-size:15px;line-height:1.55}
header{max-width:1240px;margin:0 auto;padding:22px 16px 0}h1{font-size:21px;margin:0}header p{margin:2px 0 0;color:var(--sub);font-size:13px}
nav{max-width:1240px;margin:12px auto 0;padding:0 16px;display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line)}
nav button{background:none;border:0;border-bottom:3px solid transparent;padding:10px 14px;font:inherit;color:var(--sub);cursor:pointer}
nav button.on{color:var(--ink);border-color:var(--accent);font-weight:700}
.tab{display:none;max-width:1240px;margin:0 auto;padding:16px;gap:16px;grid-template-columns:repeat(12,1fr)}.tab.on{display:grid}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;grid-column:span 12;min-width:0}
@media(min-width:900px){.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}}
h2{font-size:16px;margin:0 0 12px}h3{font-size:14px;margin:0 0 6px}.sub{color:var(--sub);font-size:13px}
.kpis{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.kpi{border:1px solid var(--line);border-radius:10px;padding:12px}.kpi b{display:block;font-size:20px}
.todo{font-size:17px;font-weight:700;color:var(--accent);margin:0;padding-left:20px}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{background:var(--chip);border-radius:999px;padding:3px 10px;font-size:12.5px}
.on-flag{color:var(--hot);font-weight:700}.off-flag{color:var(--sub)}
table{width:100%;border-collapse:collapse;font-size:13.5px}td,th{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--sub);font-weight:500}
.lv{font-weight:700}.lv.급증{color:var(--hot)}.lv.증가{color:var(--warn)}.lv.감소,.lv.보통{color:var(--sub);font-weight:500}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.sig{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}.sigc{border:1px solid var(--line);border-radius:10px;padding:12px}
.st-on{color:var(--ok);font-weight:700}.st-off{color:var(--hot);font-weight:700}
.chart{position:relative;height:230px}.chart.sm{height:170px}.chart.lg{height:340px}
details{border-top:1px solid var(--line);padding:8px 0}summary{cursor:pointer}details ul{margin:6px 0 0;padding-left:18px}
#cy{height:640px;border:1px solid var(--line);border-radius:10px;background:var(--card)}
.gwrap{display:grid;gap:12px;grid-template-columns:1fr}@media(min-width:900px){.gwrap{grid-template-columns:1fr 340px}}
#panel{border:1px solid var(--line);border-radius:10px;padding:14px;max-height:640px;overflow:auto}#panel .rel{display:block;padding:3px 0;cursor:pointer;color:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}.legend label{font-size:12.5px;display:flex;align-items:center;gap:4px;cursor:pointer}.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
input[type=search],select{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
footer{max-width:1240px;margin:0 auto;padding:4px 16px 32px;color:var(--sub);font-size:12px}
</style></head><body>
<header><h1>투자 온톨로지</h1><p id="meta"></p></header>
<nav id="nav"></nav>

<section class="tab" id="t-개요">
 <div class="card s8"><h2>오늘 할 일</h2><ul class="todo" id="todo"></ul><p class="sub">국면·이슈·역사는 이해를 돕는 정보입니다. 매매는 검증된 규칙대로만 합니다.</p>
  <div class="kpis" id="kpis" style="margin-top:14px"></div></div>
 <div class="card s4"><h2>목표 비중</h2><div class="chart sm"><canvas id="wchart" aria-label="목표 비중"></canvas></div><div id="wlist" class="chips" style="margin-top:10px"></div></div>
 <div class="card"><h2>매매 신호 · 200일선 ±3% 밴드</h2><div class="sig" id="sig"></div></div>
</section>

<section class="tab" id="t-이슈">
 <div class="card s7"><h2>이슈 레이더 · 뉴스 관심도 (최근 7일 / 이전 90일)</h2><div class="chart lg"><canvas id="echart" aria-label="테마별 관심도"></canvas></div></div>
 <div class="card s5"><h2>내 보유 자산의 이슈 노출</h2><table id="expo"></table></div>
 <div class="card"><h2>영향 경로 · 이슈가 내 보유 자산까지 이어지는 길</h2><p class="sub">관심도 상위 이슈에서 온톨로지 관계를 따라 내 보유 자산까지 가는 최단 경로(최대 4단계).</p><table id="paths"></table></div>
 <div class="card s7"><h2>테마 추이 <select id="themeSel"></select></h2><div class="chart"><canvas id="tchart" aria-label="선택 테마 관심도 추이"></canvas></div><p class="sub">GDELT 전체 뉴스 중 해당 테마 기사 비중(일별). 아래 기록은 매일 누적됩니다.</p></div>
 <div class="card s5"><h2>테마별 헤드라인</h2><div id="heads"></div></div>
</section>

<section class="tab" id="t-거시">
 <div class="card s5"><h2>거시 국면</h2><div id="flags" class="chips" style="margin-bottom:10px"></div><table id="macro"></table></div>
 <div class="card s7"><h2>거시 지표 추이 (10년)</h2><div class="chart lg"><canvas id="mchart" aria-label="물가·실업률·금리차"></canvas></div></div>
</section>

<section class="tab" id="t-온톨로지">
 <div class="card"><h2>온톨로지 지도</h2>
  <div class="legend" id="legend"></div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px"><input type="search" id="q" placeholder="대상 검색 (예: TQQQ, 대만, 오일쇼크)"><button id="fit" style="font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);cursor:pointer">전체 보기</button></div>
  <div class="gwrap"><div id="cy" role="img" aria-label="자산·국가·산업·이슈·역사의 관계 그래프"></div><div id="panel"><p class="sub">노드를 누르면 속성과 연결된 대상이 여기에 나옵니다. 굵은 테두리 = 내 보유, 주황 = 급증 이슈·켜진 국면, 보라 테두리 = 오늘과 닮은 역사.</p></div></div>
 </div>
</section>

<section class="tab" id="t-역사">
 <div class="card"><h2>오늘과 닮은 역사 국면</h2><div id="hist"></div></div>
 <div class="card"><h2>최근 자동 생성된 사건</h2><div id="evs"></div></div>
</section>

<footer>데이터: Yahoo Finance(가격) · FRED(거시) · GDELT(뉴스) · 차트 Chart.js · 지도 Cytoscape.js — 자동 생성, 투자 권유 아님.</footer>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = (v,d=1) => (v>=0?'+':'')+(v*100).toFixed(d)+'%';
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('meta').textContent = `${D.date} 종가 기준 · ${D.strategy} · 생성 ${D.generated}`;
// 탭
const TABS=['개요','이슈','거시','온톨로지','역사']; let drawn={};
nav.innerHTML = TABS.map(t=>`<button data-t="${t}">${t}</button>`).join('');
function show(t){document.querySelectorAll('.tab').forEach(s=>s.classList.toggle('on',s.id==='t-'+t));document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
 if(!drawn[t]){drawn[t]=1;({개요:drawOverview,이슈:drawIssues,거시:drawMacro,온톨로지:drawGraph,역사:drawHistory})[t]();} try{localStorage.setItem('tab',t)}catch(e){}}
nav.onclick=e=>{if(e.target.dataset.t)show(e.target.dataset.t)};
// 개요
function drawOverview(){
 todo.innerHTML = D.actions.map(a=>`<li>${esc(a)}</li>`).join('');
 const hot = Object.entries(D.events).filter(e=>e[1].ratio>=1.5).map(e=>e[0]);
 kpis.innerHTML = [['거시 경고',D.flags.join(', ')||'없음'],['급증 이슈',hot.join(', ')||'없음'],['닮은 역사',D.analogs.length+'건'],['온톨로지',D.graph.nodes.length+'개 대상 · '+D.graph.edges.length+'개 관계']]
  .map(([k,v])=>`<div class="kpi"><span class="sub">${k}</span><b>${esc(v)}</b></div>`).join('');
 const W = Object.entries(D.targets).sort((a,b)=>b[1]-a[1]); const pal=['#1f4e8c','#c2410c','#15803d','#7c3aed','#b45309','#0e7490','#be185d','#4b5563'];
 new Chart(wchart,{type:'doughnut',data:{labels:W.map(x=>x[0]),datasets:[{data:W.map(x=>+(x[1]*100).toFixed(1)),backgroundColor:pal,borderWidth:0}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}}}});
 wlist.innerHTML = W.map((x,i)=>`<span class="chip" style="border-left:6px solid ${pal[i%8]}">${x[0]} ${(x[1]*100).toFixed(1)}%</span>`).join('');
 sig.innerHTML = Object.entries(D.sleeves).map(([a,s])=>`<div class="sigc"><h3>${a} <span class="${s.on?'st-on':'st-off'}">${s.on?'보유':'청산'}</span></h3>
  <div class="sub">${s.base} 200일선 대비 ${pct(s.gap)} · 변동성 ${(s.vol*100).toFixed(0)}% · 슬리브 ${Object.entries(s.hold).map(([t,w])=>t+' '+(w*100).toFixed(0)+'%').join(', ')}</div>
  <div class="chart sm"><canvas id="c_${a}"></canvas></div></div>`).join('');
 Object.entries(D.sleeves).forEach(([a,s])=>{const c=D.charts[s.base]; if(!c) return;
  new Chart(document.getElementById('c_'+a),{type:'line',data:{labels:c.d,datasets:[
   {label:s.base,data:c.p,borderColor:css('--accent'),borderWidth:1.6,pointRadius:0},{label:'200일선',data:c.s,borderColor:css('--sub'),borderWidth:1,pointRadius:0},
   {label:'+3%',data:c.s.map(v=>v&&v*1.03),borderColor:css('--ok'),borderDash:[4,4],borderWidth:1,pointRadius:0},{label:'-3%',data:c.s.map(v=>v&&v*0.97),borderColor:css('--hot'),borderDash:[4,4],borderWidth:1,pointRadius:0}]},
   options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:6}}}}});});
}
// 이슈
function drawIssues(){
 const E = Object.entries(D.events).filter(e=>e[1].ratio!=null).sort((a,b)=>b[1].ratio-a[1].ratio);
 if(!E.length){echart.parentNode.innerHTML='<p class="sub">이슈 데이터 없음 (GDELT 수집 실패 또는 생략)</p>';}
 else new Chart(echart,{type:'bar',data:{labels:E.map(e=>e[0]),datasets:[{data:E.map(e=>+e[1].ratio.toFixed(2)),backgroundColor:E.map(e=>e[1].ratio>=1.5?css('--hot'):e[1].ratio>=1.15?css('--warn'):css('--sub'))}]},
  options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>'관심도 '+c.raw+'배'}}}}});
 expo.innerHTML='<tr><th>보유 자산</th><th>연결된 이슈</th></tr>'+Object.entries(D.exposure).map(([t,xs])=>`<tr><td><b>${t}</b></td><td>${xs.map(x=>`<span class="lv ${x.level}">${x.name}</span>`).join(', ')||'<span class="sub">-</span>'}</td></tr>`).join('');
 const P=D.graph.paths||[];
 paths.innerHTML='<tr><th>이슈</th><th>관심도</th><th>경로</th><th>보유 자산</th></tr>'+P.map(p=>`<tr><td><b>${esc(p.theme)}</b></td><td><span class="lv ${p.level}">${p.ratio.toFixed(2)}배</span></td><td>${esc(p.text)}</td><td><b>${esc(p.asset)}</b></td></tr>`).join('')||'<tr><td class="sub">경로 없음</td></tr>';
 const names=Object.keys(D.events); themeSel.innerHTML=names.map(n=>`<option>${n}</option>`).join(''); let tc;
 const drawT=n=>{const s=D.events[n].series||[]; tc&&tc.destroy(); tc=new Chart(tchart,{type:'line',data:{labels:s.map(x=>x.d),datasets:[{label:n,data:s.map(x=>x.v),borderColor:css('--accent'),pointRadius:0,borderWidth:1.6,fill:false}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:6}}}}})};
 if(names.length){themeSel.value=E.length?E[0][0]:names[0]; drawT(themeSel.value); themeSel.onchange=()=>drawT(themeSel.value);}
 heads.innerHTML=E.map(([n,e])=>`<details ${e.ratio>=1.15?'open':''}><summary>${n} · <span class="lv ${e.level}">${e.level}</span> <span class="sub">${e.ratio.toFixed(2)}배</span></summary><div class="sub">영향: ${e.links.join(', ')}</div>
  <ul>${e.headlines.map(h=>`<li><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a> <span class="sub">${esc(h.domain)}</span></li>`).join('')||'<li class="sub">헤드라인은 관심도 상위 테마만 수집</li>'}</ul></details>`).join('');
}
// 거시
function drawMacro(){
 flags.innerHTML=Object.entries(D.regime_rules).map(([k,r])=>`<span class="chip ${D.flags.includes(k)?'on-flag':'off-flag'}" title="${esc(r)}">${D.flags.includes(k)?'●':'○'} ${k}</span>`).join('');
 macro.innerHTML=Object.entries(D.macro).map(([k,v])=>`<tr><th>${k}</th><td>${esc(v)}</td></tr>`).join('')+Object.entries(D.regime_rules).map(([k,r])=>`<tr><th>${k} 기준</th><td class="sub">${esc(r)}</td></tr>`).join('');
 const M=D.macro_series; new Chart(mchart,{type:'line',data:{labels:M.d,datasets:[
  {label:'물가상승률(%)',data:M.cpi,borderColor:css('--hot'),pointRadius:0,borderWidth:1.6},{label:'실업률(%)',data:M.unrate,borderColor:css('--accent'),pointRadius:0,borderWidth:1.6},
  {label:'장단기 금리차(%p)',data:M.curve,borderColor:css('--ok'),pointRadius:0,borderWidth:1.6}]},options:{maintainAspectRatio:false,scales:{x:{ticks:{maxTicksLimit:8}}}}});
}
// 온톨로지 지도
const TC={'전략':'#111827','자산':'#1f4e8c','국가':'#0e7490','지역':'#0e7490','산업':'#7c3aed','원자재':'#b45309','요인':'#4b5563','기관':'#be185d','기업':'#9333ea','이슈':'#c2410c','사건':'#dc2626','국면':'#64748b','역사':'#15803d'};
function drawGraph(){
 const G=D.graph, hidden=new Set();
 legend.innerHTML=G.types.map(t=>`<label><input type="checkbox" checked data-t="${t}"><span class="dot" style="background:${TC[t]}"></span>${t}</label>`).join('');
 const els=[...G.nodes.map(n=>{const p=n.props||{};return {data:{id:n.id,label:n.id,type:n.type,held:!!p['보유'],hot:(p['관심도']||0)>=1.5||p['켜짐']===true,sim:!!p['오늘과닮음']}}}),
  ...G.edges.map((e,i)=>({data:{id:'e'+i,source:e.source,target:e.target,rel:e.rel}}))];
 const cy=cytoscape({container:document.getElementById('cy'),elements:els,wheelSensitivity:0.25,
  style:[{selector:'node',style:{'background-color':n=>TC[n.data('type')]||'#888','label':'data(label)','font-size':10,'color':css('--ink'),'text-valign':'bottom','text-margin-y':3,'width':14,'height':14,'font-family':'Noto Sans KR'}},
   {selector:'node[?held]',style:{'border-width':4,'border-color':css('--accent'),'width':22,'height':22,'font-weight':700}},
   {selector:'node[?hot]',style:{'background-color':css('--hot'),'width':20,'height':20}},
   {selector:'node[?sim]',style:{'border-width':4,'border-color':'#7c3aed'}},
   {selector:'node[type="전략"]',style:{'width':28,'height':28,'font-size':12,'font-weight':700}},
   {selector:'edge',style:{'width':1,'line-color':css('--line'),'curve-style':'bezier','target-arrow-shape':'triangle','target-arrow-color':css('--line'),'arrow-scale':0.6}},
   {selector:'.faded',style:{'opacity':0.12}},{selector:'edge.hl',style:{'line-color':css('--accent'),'target-arrow-color':css('--accent'),'width':2,'label':'data(rel)','font-size':9,'color':css('--sub')}}],
  layout:{name:'cose',animate:false,nodeRepulsion:9000,idealEdgeLength:70,randomize:false}});
 const focus=id=>{const n=cy.getElementById(id); if(!n.length) return; cy.elements().removeClass('faded hl'); const nb=n.closedNeighborhood();
  cy.elements().not(nb).addClass('faded'); nb.edges().addClass('hl'); cy.animate({fit:{eles:nb,padding:60}},{duration:300}); panelFor(id);};
 const panelFor=id=>{const node=G.nodes.find(x=>x.id===id); const p=node.props||{};
  const out=G.edges.filter(e=>e.source===id), inc=G.edges.filter(e=>e.target===id);
  const props=Object.entries(p).filter(([k,v])=>v!==''&&v!=null&&!(Array.isArray(v)&&!v.length)).map(([k,v])=>`<tr><th>${esc(k)}</th><td>${Array.isArray(v)?v.map(esc).join('<br>'):esc(v)}</td></tr>`).join('');
  const rel=(arr,key,arrow)=>arr.map(e=>`<a class="rel" data-id="${esc(e[key])}">${arrow} ${esc(e.rel)} · ${esc(e[key])}</a>`).join('');
  panel.innerHTML=`<h3>${esc(id)}</h3><span class="chip">${node.type}</span><table style="margin:10px 0">${props}</table><h3>나가는 관계</h3>${rel(out,'target','→')||'<span class="sub">없음</span>'}<h3 style="margin-top:10px">들어오는 관계</h3>${rel(inc,'source','←')||'<span class="sub">없음</span>'}`;
  panel.querySelectorAll('.rel').forEach(a=>a.onclick=()=>focus(a.dataset.id));};
 cy.on('tap','node',e=>focus(e.target.id())); cy.on('tap',e=>{if(e.target===cy){cy.elements().removeClass('faded hl');}});
 legend.onchange=e=>{const t=e.target.dataset.t; e.target.checked?hidden.delete(t):hidden.add(t); cy.nodes().forEach(n=>n.style('display',hidden.has(n.data('type'))?'none':'element'));};
 q.oninput=()=>{const s=q.value.trim(); if(!s) return; const m=cy.nodes().filter(n=>n.id().includes(s)); if(m.length) focus(m[0].id());};
 fit.onclick=()=>{cy.elements().removeClass('faded hl'); cy.fit(undefined,30);};
 const held=G.nodes.find(n=>n.type==='전략'); if(held) setTimeout(()=>focus(held.id),50);
}
// 역사
function drawHistory(){
 hist.innerHTML=D.analogs.map(h=>`<details open><summary><b>${esc(h.name)}</b> <span class="sub">· ${esc(h.why)}</span></summary><p>${esc(h.text)}</p></details>`).join('')||'<p class="sub">현재 국면·이슈와 닮은 역사 국면 없음</p>';
 const ev=D.graph.nodes.filter(n=>n.type==='사건');
 evs.innerHTML=ev.map(n=>`<details><summary>${esc(n.id)}</summary><ul>${(n.props['헤드라인']||[]).map(h=>`<li>${esc(h)}</li>`).join('')}</ul></details>`).join('')||'<p class="sub">오늘 새로 생긴 사건 없음 (관심도 1.5배 이상 급증 시 자동 생성)</p>';
}
let start='개요'; try{start=localStorage.getItem('tab')||'개요'}catch(e){} show(TABS.includes(start)?start:'개요');
</script></body></html>"""


def write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False, default=str)), encoding='utf-8')
