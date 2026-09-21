const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST':'GET', headers:{'Content-Type':'application/json'}, body:body?JSON.stringify(body):undefined});
  const j = await r.json(); if(!r.ok) throw new Error(j.error||'Falha na operação'); return j;
}
async function login(){try{await api('/api/login',{password:$('#password').value});$('#login').hidden=true;$('#app').hidden=false;loadSummary()}catch(e){$('#loginMsg').textContent=e.message}}
$$('.tab').forEach(b=>b.onclick=()=>{$$('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.tab).classList.add('active');if(b.dataset.tab==='bankroll')loadSummary()});
function formData(form){const d=Object.fromEntries(new FormData(form));d.completed_hand=form.elements.completed_hand?.checked===true;return d}
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let reviewRevision=0;
function invalidateReview(){reviewRevision++;$('#result').hidden=true}
let positionOrder={};
function seatLayout(count){return Array.from({length:count},(_,i)=>{const angle=2*Math.PI*i/count;return [50-39*Math.sin(angle),50+40*Math.cos(angle)]})}
let playerCount=8,dealerSeat=0,activeCardSlot='card1';
function renderTable(){
  if(!positionOrder[playerCount])return;
  const seats=$('#seats');seats.innerHTML='';
  $('#pokerTable').dataset.players=playerCount;
  seatLayout(playerCount).forEach(([x,y],i)=>{
    const offset=(i-dealerSeat+playerCount)%playerCount,pos=positionOrder[playerCount][offset];
    const b=document.createElement('button');b.type='button';b.className='seat'+(i===0?' hero':'')+(i===dealerSeat?' dealer':'');b.style.left=x+'%';b.style.top=y+'%';
    b.innerHTML=`<span class="avatar">${i===0?'VOCÊ':'♟'}</span><b>${pos}</b>${i===dealerSeat?'<i>D</i>':''}`;
    b.setAttribute('aria-label',`${i===0?'Você':`Assento ${i+1}`}, ${pos}. Colocar botão aqui`);b.setAttribute('aria-pressed',String(i===dealerSeat));
    b.onclick=()=>{dealerSeat=i;invalidateReview();renderTable()};seats.appendChild(b);
  });
  const heroOffset=(playerCount-dealerSeat)%playerCount,heroPos=positionOrder[playerCount][heroOffset];
  $('#heroPosition').textContent=heroPos;$('#reviewForm').elements.position.value=heroPos;
  $('#reviewForm').elements.player_count.value=playerCount;
  $('#tableHint').textContent=playerCount===2?'Heads-up: o botão também é o small blind e age primeiro no pré-flop.':'Escolha quantos jogadores receberam cartas no início da mão, incluindo você. LJ é o assento antes do HJ.';
  $$('.player-count').forEach(b=>{const selected=Number(b.dataset.count)===playerCount;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected))});
  syncContext();
}
function choosePlayerCount(count){playerCount=count;dealerSeat=Math.min(dealerSeat,count-1);invalidateReview();renderTable();try{localStorage.setItem('pokercoach.playerCount',String(count))}catch(e){}}
async function initTable(){try{positionOrder=await api('/positions.json');const controls=$('#playerCounts');controls.innerHTML='';Object.keys(positionOrder).forEach(count=>{const b=document.createElement('button');b.type='button';b.className='player-count';b.dataset.count=count;b.textContent=count;b.setAttribute('aria-label',`${count} jogadores`);b.onclick=()=>choosePlayerCount(Number(count));controls.appendChild(b)});try{const saved=Number(localStorage.getItem('pokercoach.playerCount'));if(positionOrder[saved])playerCount=saved}catch(e){}renderTable();$('.analyze-btn').disabled=false}catch(e){$('#tableHint').textContent='Não foi possível carregar a mesa. Atualize a página.'}}
$$('.choice').forEach(b=>b.onclick=()=>{$$(`.choice[data-field="${b.dataset.field}"]`).forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#reviewForm').elements[b.dataset.field].value=b.dataset.value;invalidateReview();syncContext()});
$$('.action-choice').forEach(b=>b.onclick=()=>{$$('.action-choice').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#reviewForm').elements.situation.value=b.dataset.value;invalidateReview();syncContext()});
function toggleInputs(selector,shown){const node=$(selector);node.hidden=!shown;node.querySelectorAll('input,select').forEach(i=>i.disabled=!shown)}
function syncContext(){
  const f=$('#reviewForm').elements,preflop=f.street.value==='preflop';
  toggleInputs('#raiseInputs',preflop&&f.situation.value==='facing_raise');
  toggleInputs('#postflopInputs',!preflop);
  toggleInputs('#tournamentContext',f.mode.value==='tournament');
  $$('.action-choice').forEach(b=>b.disabled=!preflop);
  if(!positionOrder[playerCount])return;
  const positions=positionOrder[playerCount],order=playerCount===2?positions:[...positions.slice(3),...positions.slice(0,3)];
  const previous=f.opener_position.value,options=order.slice(0,order.indexOf(f.position.value));
  f.opener_position.innerHTML='<option value="">Selecione a posição</option>'+options.map(p=>`<option value="${p}">${p}</option>`).join('');
  if(options.includes(previous))f.opener_position.value=previous;
}
$('#reviewForm').addEventListener('input',e=>{invalidateReview();if(e.target.id!=='studyPreset')$('#studyPreset').value=''});
$('#reviewForm').addEventListener('change',e=>{invalidateReview();if(e.target.id!=='studyPreset')syncContext()});
$('#studyPreset').onchange=e=>{
  const presets={cash6:['cash',6,100],cash8:['cash',8,100],mtt100:['tournament',9,100],mtt75:['tournament',9,75],mtt10:['tournament',8,10]},p=presets[e.target.value];if(!p||!positionOrder[p[1]])return;
  const f=$('#reviewForm').elements;f.mode.value=p[0];f.stack_bb.value=p[2];f.street.value='preflop';f.situation.value='unopened';f.ante_bb.value=0;f.icm_context.value='none';dealerSeat=0;
  $$('.choice').forEach(b=>b.classList.toggle('active',b.dataset.value===p[0]));$$('.action-choice').forEach(b=>b.classList.toggle('active',b.dataset.value==='unopened'));choosePlayerCount(p[1]);
};
$('#advancedToggle').onclick=()=>{const a=$('#advanced');a.hidden=!a.hidden;$('#advancedToggle span').textContent=a.hidden?'⌄':'⌃'};
const suitData=[['s','♠','black'],['h','♥','red'],['d','♦','red'],['c','♣','black']],ranks=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];
function buildDeck(){const deck=$('#deck');deck.innerHTML='';ranks.forEach(rank=>suitData.forEach(([code,symbol,color])=>{const card=rank+code.toUpperCase(),btn=document.createElement('button');btn.type='button';btn.className=`pick-card ${color}`;btn.dataset.card=card;btn.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;btn.onclick=()=>selectCard(card,rank,symbol,color);deck.appendChild(btn)}))}
function openPicker(slot){activeCardSlot=slot;$('#pickerLabel').textContent=slot==='card1'?'Primeira carta':'Segunda carta';$$('.pick-card').forEach(b=>{const other=slot==='card1'?$('#reviewForm').elements.card2.value:$('#reviewForm').elements.card1.value;b.disabled=b.dataset.card===other});$('#cardPicker').hidden=false}
function selectCard(card,rank,symbol,color){invalidateReview();$('#reviewForm').elements[activeCardSlot].value=card;const slot=$(`.card-slot[data-slot="${activeCardSlot}"]`);slot.className=`card-slot selected ${color}`;slot.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;$('#cardPicker').hidden=true}
$$('.card-slot').forEach(b=>b.onclick=()=>openPicker(b.dataset.slot));$('#closePicker').onclick=()=>$('#cardPicker').hidden=true;$('#cardPicker').onclick=e=>{if(e.target.id==='cardPicker')e.currentTarget.hidden=true};
function rangeGrid(r){
  if(!r.range_hands?.length)return '';
  const included=new Set(r.range_hands);let cells='';
  ranks.forEach((a,i)=>ranks.forEach((b,j)=>{const hand=i===j?a+b:i<j?a+b+'s':b+a+'o';cells+=`<span class="range-cell ${included.has(hand)?'included':''} ${hand===r.hand?'selected-hand':''}" title="${hand}: ${included.has(hand)?'no conjunto da fonte':'fora do conjunto'}">${hand}</span>`}));
  return `<details class="range-details"><summary>Ver range gráfico e notação</summary><p>Verde: conjunto consultado. Borda dourada: sua mão. Cinza: fora do conjunto; em 3-bet, isso não significa fold automático.</p><div class="range-grid">${cells}</div><p class="range-notation">${escapeHTML(r.range)}</p></details>`;
}
$('#reviewForm').onsubmit=async e=>{
  e.preventDefault();const box=$('#result'),f=e.target.elements;
  if(!f.card1.value||!f.card2.value){box.hidden=false;box.innerHTML='<p class="error">Escolha as duas cartas.</p>';return}
  if(!$('#studyConfirm').checked){box.hidden=false;box.innerHTML='<p class="error">Confirme que é uma simulação ou mão encerrada.</p>';return}
  const data=formData(e.target);data.completed_hand=true;data.icm_pressure=f.icm_context.value==='none'?false:true;data.closes_action=f.closes_action.checked;
  const revision=++reviewRevision;$('.analyze-btn').disabled=true;
  try{const r=await api('/api/analyze',data);if(revision!==reviewRevision)return;
    const sources=(r.sources||[]).map(s=>`<a href="${escapeHTML(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(s.title)}</a>`).join(' · ');
    box.innerHTML=`<div class="decision ${escapeHTML(r.action.toLowerCase().replaceAll(' ','-'))}">${escapeHTML(r.action)}</div><h2>${escapeHTML(r.hand)} · ${escapeHTML(r.sizing)}</h2><p><b>${escapeHTML(r.profile)}</b></p><p>Mesa de ${r.player_count} · ${escapeHTML(r.position)}${r.additional_bb!=null?` · Acrescentar ${r.additional_bb} BB`:''}</p><ul>${r.notes.map(n=>`<li>${escapeHTML(n)}</li>`).join('')}</ul>${rangeGrid(r)}<p class="source-links">${sources}</p><small>${escapeHTML(r.disclaimer)}</small>`;
    box.hidden=false;box.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){if(revision===reviewRevision){box.hidden=false;box.innerHTML=`<p class="error">${escapeHTML(err.message)}</p>`}}finally{$('.analyze-btn').disabled=false}
};
$('#sessionForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/session',formData(e.target));e.target.reset();e.target.played_at.value=new Date().toISOString().slice(0,10);loadSummary()}catch(err){alert(err.message)}};
async function loadSummary(){try{const s=await api('/api/summary');$('#summary').innerHTML=`<div class="kpis"><div><b>${s.sessions}</b><span>Sessões</span></div><div><b>${Number(s.profit).toFixed(2)}</b><span>Resultado</span></div><div><b>${Number(s.invested).toFixed(2)}</b><span>Total entradas</span></div></div><h3>Últimas sessões</h3>${s.recent.length?`<div class="table"><table><tr><th>Data</th><th>Modo</th><th>Limite</th><th>Entrada</th><th>Saída</th></tr>${s.recent.map(x=>`<tr><td>${x[0]}</td><td>${x[1]}</td><td>${x[2]}</td><td>${x[3]}</td><td>${x[4]}</td></tr>`).join('')}</table></div>`:'<p>Nenhuma sessão registrada.</p>'}`}catch(e){}}
$('#sessionForm').played_at.value=new Date().toISOString().slice(0,10);
buildDeck();initTable();
