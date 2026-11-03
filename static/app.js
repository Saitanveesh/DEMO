'use strict';
/* Crypto Cyber Hunt — local, dependency-free live dashboard. */
const $=id=>document.getElementById(id);
const svgNS='http://www.w3.org/2000/svg';
const chartColors=['#40e4c4','#70b8ff','#f9bd68','#c39bff','#ff8ea4'];
function cell(text){const td=document.createElement('td');td.textContent=String(text);return td;}
function svgEl(tag,attrs={},text){const node=document.createElementNS(svgNS,tag);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));if(text!==undefined)node.textContent=String(text);return node;}
const eventClock={state:null,origin:0,server:0,lastIdentity:null};
function remainingSeconds(){if(!eventClock.state?.active)return 0;return Math.max(0,Math.ceil(eventClock.state.end_epoch-(eventClock.server+(performance.now()-eventClock.origin)/1000)));}
function padClock(seconds){const h=Math.floor(seconds/3600),m=Math.floor(seconds%3600/60),s=seconds%60;return h?`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;}
function tickClock(){
 const s=eventClock.state;if(!s)return;
 const left=remainingSeconds();const live=s.active&&left>0;
 const strip=$('round-strip');const title=$('round-strip-title'),counter=$('round-countdown'),status=$('round-strip-status'),admin=$('admin-round-countdown');
 if(strip){strip.classList.toggle('is-live',live);strip.classList.toggle('urgent',live&&left<=60);}
 if(title)title.textContent=live?`${s.title} · ${s.active_challenges} MISSIONS`:(s.state==='expired'?'ROUND COMPLETE · WAIT FOR ORGANIZER':s.state==='ended'?'ROUND ENDED · AWAIT NEXT RELEASE':'NEXT ROUND AWAITING DEPLOYMENT');
 if(counter)counter.textContent=live?padClock(left):'--:--';
 if(status)status.textContent=live?(left<=60?'FINAL MINUTE':'TIME REMAINING'):'LOCKED';
 if(admin)admin.textContent=padClock(left);
 const form=document.querySelector('.mission form[action$="/submit"]');
 if(form&&!live){form.querySelectorAll('input,button').forEach(n=>n.disabled=true);if(!$('round-locked')){const msg=document.createElement('p');msg.id='round-locked';msg.className='notice';msg.textContent='Round closed. Flag submission is no longer available.';form.before(msg);}}
}
async function pollEvent(){
 try{
  const res=await fetch('/api/event',{cache:'no-store'});if(!res.ok)throw Error('event offline');
  const state=await res.json();const ident=`${state.round_id}:${state.state}:${state.active}`;
  const previous=eventClock.lastIdentity;
  eventClock.state=state;eventClock.origin=performance.now();eventClock.server=state.server_epoch;eventClock.lastIdentity=ident;
  tickClock();
  if(previous!==null&&ident!==previous&&location.pathname==='/challenges')location.reload();
 }catch(e){if($('round-strip-status'))$('round-strip-status').textContent='RECONNECTING';}
}
if($('round-strip')){pollEvent();setInterval(pollEvent,5000);setInterval(tickClock,250);}

function drawGraph(history){
 const svg=$('score-graph'),legend=$('graph-legend');if(!svg||!legend)return;
 svg.replaceChildren();legend.replaceChildren();
 const all=(history||[]).flatMap(s=>s.points||[]);const w=900,h=290,left=68,right=22,top=24,bottom=43;
 const lo=Math.min(...all.map(x=>x.at),Date.now()/1000),hi=Math.max(...all.map(x=>x.at),Date.now()/1000);
 const minX=Number.isFinite(lo)?lo-10:0,maxX=Number.isFinite(hi)?Math.max(hi,minX+60):60;
 const ymax=Math.max(50,...all.map(x=>x.score||0));const ymin=Math.min(0,...all.map(x=>x.score||0));
 const ceiling=Math.ceil(ymax/50)*50, floor=Math.floor(ymin/50)*50;
 const x=t=>left+((t-minX)/Math.max(1,maxX-minX))*(w-left-right), y=v=>h-bottom-((v-floor)/Math.max(1,ceiling-floor))*(h-top-bottom);
 svg.append(svgEl('rect',{x:0,y:0,width:w,height:h,fill:'transparent'}));
 for(let i=0;i<=4;i++){
  const score=floor+(ceiling-floor)*i/4,yp=y(score);
  svg.append(svgEl('line',{x1:left,x2:w-right,y1:yp,y2:yp,stroke:'#314352','stroke-width':1,'stroke-dasharray':i===0?'0':'4 7',opacity:.65}));
  svg.append(svgEl('text',{x:left-13,y:yp+4,'text-anchor':'end',class:'axis-text'},Math.round(score)));
 }
 for(let i=0;i<=4;i++){
  const time=minX+(maxX-minX)*i/4;
  svg.append(svgEl('text',{x:x(time),y:h-14,'text-anchor':'middle',class:'axis-text'},new Date(time*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})));
 }
 let drew=false;
 (history||[]).forEach((team,i)=>{
  const color=chartColors[i%chartColors.length],entries=team.points||[];
  const legendItem=document.createElement('div');legendItem.className='legend-item';
  const dot=document.createElement('span');dot.className='legend-dot';dot.style.backgroundColor=color;
  const name=document.createElement('span');name.textContent=team.team;legendItem.append(dot,name);legend.append(legendItem);
  if(entries.length<=1)return;
  drew=true;let points=[...entries].sort((a,b)=>a.at-b.at).map(p=>[x(p.at),y(p.score)]);
  const end=points[points.length-1];points.push([x(maxX),end[1]]);
  let d=`M${points[0][0]},${points[0][1]}`;
  for(let j=1;j<points.length;j++)d+=` H${points[j][0]} V${points[j][1]}`;
  svg.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':3.2,'stroke-linecap':'round','stroke-linejoin':'round'}));
  for(const [px,py] of points.slice(1,-1))svg.append(svgEl('circle',{cx:px,cy:py,r:4.2,fill:color,stroke:'#101d2a','stroke-width':2}));
 });
 if(!drew)svg.append(svgEl('text',{x:w/2,y:h/2,'text-anchor':'middle',class:'chart-empty'},'SCORE HISTORY APPEARS AFTER FIRST SOLVE OR PAID CLUE'));
}
function updatePodium(leaders){const podium=$('podium');if(!podium)return;podium.replaceChildren();
 for(const [i,p] of leaders.slice(0,3).entries()){
  const card=document.createElement('div');card.className='podium-card podium-'+(i+1);
  const rank=document.createElement('span');rank.className='podium-rank';rank.textContent=`#${i+1}`;
  const team=document.createElement('strong');team.textContent=p.team||p.username;
  const meta=document.createElement('span');meta.textContent=`${p.members||1} MEMBERS · ${p.solves} SOLVES · −${p.hint_penalty||0} HINT PTS`;
  const points=document.createElement('b');points.textContent=`${p.score} PTS`;
  card.append(rank,team,meta,points);podium.append(card);
 }
}
async function reloadScores(){
 const body=$('leaderboard');if(!body)return;const indicator=$('score-status');
 try{
  const res=await fetch('/api/scoreboard',{cache:'no-store'});if(!res.ok)throw Error(res.status);
  const data=await res.json();body.replaceChildren();updatePodium(data.ranking);drawGraph(data.history);
  data.ranking.forEach(team=>{const tr=document.createElement('tr');tr.append(cell(String(team.rank).padStart(2,'0')),cell(`${team.team||team.username} · ${team.members||1} member(s)`),cell(`${team.solves} · ${team.hints_used||0} clues`),cell(`${team.score} pts (−${team.hint_penalty||0} clues)`));body.append(tr);});
  if(!data.ranking.length){const tr=document.createElement('tr');const td=cell('Team registrations will appear here.');td.colSpan=4;tr.append(td);body.append(tr);}
  indicator.textContent=(data.frozen?'PUBLIC LEADERBOARD FROZEN · ':'SYNCED · ')+new Date(data.updated).toLocaleTimeString();
 }catch(e){indicator.textContent='Connection interrupted; reconnecting…';}
}
async function reloadAdmin(){
 const metrics=$('admin-metrics'),feed=$('admin-feed');if(!metrics||!feed)return;
 try{
  const res=await fetch('/api/admin',{cache:'no-store'});if(!res.ok)throw Error(res.status);const d=await res.json();
  metrics.textContent=`${d.teams} teams · ${d.members} members · ${d.solves} solves · ${d.hints_unlocked||0} clues · −${d.points_spent||0} hint pts · ${d.attempts} attempts`;
  feed.replaceChildren();for(const s of d.recent){const row=document.createElement('div');row.className='feed-item';const desc=document.createElement('div');desc.textContent=`${s.team} · ${s.title}`;const state=document.createElement('span');state.textContent=s.kind==='hint'?`CLUE −${s.cost} PTS`:s.correct?'SOLVED':'INCORRECT';state.className=s.kind==='hint'?'hint-event':s.correct?'ok':'bad';row.append(desc,state);feed.append(row);}
  if(!d.recent.length)feed.textContent='Waiting for the first flag submission.';
  if(d.round&&d.round.state==='expired'&&$('admin-round-countdown'))location.reload();
 }catch(e){metrics.textContent='Connection interrupted; retrying…';}
}
if($('leaderboard')){reloadScores();setInterval(reloadScores,5000);}
if($('admin-metrics')){reloadAdmin();setInterval(reloadAdmin,3000);}
const selection=$('selection-count'),releaseForm=document.querySelector('form.deploy-form');
if(selection&&releaseForm){const items=[...releaseForm.querySelectorAll('input[name^="pick_"]')];const update=()=>{const n=items.filter(i=>i.checked).length;selection.textContent=`${n} selected`;selection.classList.toggle('ready',n>0);};items.forEach(x=>x.addEventListener('change',update));update();releaseForm.addEventListener('submit',e=>{const n=items.filter(i=>i.checked).length;if(!n){e.preventDefault();alert('Select at least one challenge.');return;}if(!confirm(`Deploy ${n} challenge(s) now? The server-side timer starts immediately and cannot be paused.`))e.preventDefault();});}
const endForm=document.querySelector('form.round-end-form');if(endForm)endForm.addEventListener('submit',e=>{if(!confirm('End the current round now? All remaining submissions will be blocked.'))e.preventDefault();});
const uploadButton=$('upload-button');
if(uploadButton)uploadButton.addEventListener('click',async()=>{
 const input=$('upload-file'),status=$('upload-status'),file=input.files?.[0];if(!file){status.textContent='Select a file first.';return;}
 if(file.size>3000000){status.textContent='Maximum file size is 3 MB.';return;}
 uploadButton.disabled=true;status.textContent='Uploading evidence…';
 try{
  const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('File read failed'));reader.readAsDataURL(file);});
  const csrf=document.querySelector('input[name="_csrf"]')?.value;
  const res=await fetch('/admin/upload',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({name:file.name,data:String(dataUrl).split(',')[1]})});
  if(!res.ok)throw Error(`Upload failed (${res.status})`);const data=await res.json();$('asset_name').value=data.asset_name;
  status.textContent=`Uploaded ${file.name} (${data.bytes} bytes). Save the challenge.`;
 }catch(e){status.textContent=String(e.message||e);}finally{uploadButton.disabled=false;}
});

// A paid clue is a permanent team-level score debit; make the confirmation explicit.
document.querySelectorAll('form.hint-unlock-form').forEach(form=>{
 form.addEventListener('submit',event=>{
  const label=form.querySelector('button')?.textContent||'';
  if(label.includes('−')&&!confirm(`${label}? This deduction affects your team's live score immediately and cannot be refunded.`))event.preventDefault();
 });
});
