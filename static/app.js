'use strict';
function cell(text) {const x=document.createElement('td');x.textContent=String(text);return x;}
async function reloadScores(){
 const body=document.getElementById('leaderboard');if(!body)return;
 const indicator=document.getElementById('score-status');
 try {const r=await fetch('/api/scoreboard',{cache:'no-store'});if(!r.ok)throw Error(r.status);const payload=await r.json();body.replaceChildren();
  for(const p of payload.ranking){const tr=document.createElement('tr');tr.append(cell(String(p.rank).padStart(2,'0')),cell(p.username),cell(p.solves+' solved'),cell(p.score));body.appendChild(tr);}
  if(!payload.ranking.length){const tr=document.createElement('tr'),td=cell('No rankings yet.');td.colSpan=4;tr.append(td);body.appendChild(tr);}
  indicator.textContent=(payload.frozen?'PUBLIC SCOREBOARD FROZEN · ':'Last update · ')+new Date(payload.updated).toLocaleTimeString();
 }catch(e){indicator.textContent='Connection unavailable; retrying automatically.';}
}
async function reloadAdmin(){
 const metrics=document.getElementById('admin-metrics'),feed=document.getElementById('admin-feed');if(!metrics||!feed)return;
 try{const r=await fetch('/api/admin',{cache:'no-store'});if(!r.ok)throw Error(r.status);const v=await r.json();metrics.textContent=`${v.participants} participants · ${v.solves} solves · ${v.attempts} submissions`;
 feed.replaceChildren();for(const s of v.recent){const row=document.createElement('div');row.className='feed-item';const desc=document.createElement('div');desc.textContent=s.username+' · '+s.title;const state=document.createElement('span');state.textContent=s.correct?'SOLVED':'INCORRECT';state.className=s.correct?'ok':'bad';row.append(desc,state);feed.append(row);}
 if(!v.recent.length)feed.textContent='No submissions yet.';
 }catch(e){metrics.textContent='Connection interrupted; retrying.';}
}
if(document.getElementById('leaderboard')){reloadScores();setInterval(reloadScores,5000)}
if(document.getElementById('admin-metrics')){reloadAdmin();setInterval(reloadAdmin,3000)}

const uploadButton=document.getElementById('upload-button');
if(uploadButton){uploadButton.addEventListener('click',async()=>{
 const fileInput=document.getElementById('upload-file'),status=document.getElementById('upload-status');
 const file=fileInput.files?.[0];
 if(!file){status.textContent='Select a file first.';return;}
 if(file.size>3000000){status.textContent='The file exceeds 3 MB.';return;}
 uploadButton.disabled=true;status.textContent='Uploading evidence…';
 try{
  const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('File read failed'));reader.readAsDataURL(file);});
  const csrf=document.querySelector('input[name="_csrf"]')?.value;
  const r=await fetch('/admin/upload',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({name:file.name,data:String(dataUrl).split(',',2)[1]})});
  if(!r.ok)throw Error(`Upload failed (${r.status})`);
  const result=await r.json();document.getElementById('asset_name').value=result.asset_name;
  status.textContent=`Uploaded ${file.name} (${result.bytes} bytes). Save the challenge to attach it.`;
 }catch(e){status.textContent=String(e.message||e);}finally{uploadButton.disabled=false;}
});}