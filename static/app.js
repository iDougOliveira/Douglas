const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

async function api(path, body) {
  const r = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: {'Content-Type':'application/json'},
    body: body ? JSON.stringify(body) : undefined
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || 'Falha na operação');
  return j;
}

async function login(){
  try{
    await api('/api/login',{password:$('#password').value});
    $('#login').hidden=true;
    $('#app').hidden=false;
    loadSummary();
  }catch(e){ $('#loginMsg').textContent=e.message; }
}

$$('.tab').forEach(b=>b.onclick=()=>{
  $$('.tab,.panel').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  $('#'+b.dataset.tab).classList.add('active');
  if(b.dataset.tab==='bankroll') loadSummary();
});

function formData(form){
  const d=Object.fromEntries(new FormData(form));
  d.completed_hand=true;
  return d;
}

const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));

let reviewRevision=0;
let autoTimer=null;
let positionOrder={};
let playerCount=8;
let dealerSeat=0;
let activeCardSlot='card1';
let selectedSuit=null;

const boardFields=['flop1','flop2','flop3','turn','river'];
const suitData=[
  ['S','♠','black','Espadas'],
  ['H','♥','red','Copas'],
  ['D','♦','red','Ouros'],
  ['C','♣','black','Paus']
];
const ranks=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];

function invalidateReview(message='Atualizando decisão…'){
  reviewRevision++;
  $('#autoStatus').textContent=message;
}

function seatLayout(count){
  return Array.from({length:count},(_,i)=>{
    const angle=2*Math.PI*i/count;
    return [50-39*Math.sin(angle),50+40*Math.cos(angle)];
  });
}

function renderTable(){
  if(!positionOrder[playerCount]) return;
  const seats=$('#seats');
  seats.innerHTML='';
  $('#pokerTable').dataset.players=playerCount;

  seatLayout(playerCount).forEach(([x,y],i)=>{
    const offset=(i-dealerSeat+playerCount)%playerCount;
    const pos=positionOrder[playerCount][offset];
    const b=document.createElement('button');
    b.type='button';
    b.className='seat'+(i===0?' hero':'')+(i===dealerSeat?' dealer':'');
    b.style.left=x+'%';
    b.style.top=y+'%';
    b.innerHTML=`<span class="avatar">${i===0?'VOCÊ':'♟'}</span><b>${pos}</b>${i===dealerSeat?'<i>D</i>':''}`;
    b.setAttribute('aria-label',`${i===0?'Você':`Assento ${i+1}`}, ${pos}. Colocar botão aqui`);
    b.setAttribute('aria-pressed',String(i===dealerSeat));
    b.onclick=()=>{
      dealerSeat=i;
      invalidateReview();
      renderTable();
      scheduleAnalysis();
    };
    seats.appendChild(b);
  });

  const heroOffset=(playerCount-dealerSeat)%playerCount;
  const heroPos=positionOrder[playerCount][heroOffset];
  $('#heroPosition').textContent=heroPos;
  $('#reviewForm').elements.position.value=heroPos;
  $('#reviewForm').elements.player_count.value=playerCount;
  $('#tableHint').textContent=playerCount===2
    ?'Heads-up: o botão também é o small blind.'
    :'Clique em qualquer assento para posicionar o botão. O motor identifica sua posição automaticamente.';

  $$('.player-count').forEach(b=>{
    const selected=Number(b.dataset.count)===playerCount;
    b.classList.toggle('active',selected);
    b.setAttribute('aria-pressed',String(selected));
  });
  syncContext();
}

function choosePlayerCount(count){
  playerCount=count;
  dealerSeat=Math.min(dealerSeat,count-1);
  invalidateReview();
  renderTable();
  try{localStorage.setItem('pokercoach.playerCount',String(count))}catch(e){}
  scheduleAnalysis();
}

async function initTable(){
  try{
    positionOrder=await api('/positions.json');
    const controls=$('#playerCounts');
    controls.innerHTML='';
    Object.keys(positionOrder).forEach(count=>{
      const b=document.createElement('button');
      b.type='button';
      b.className='player-count';
      b.dataset.count=count;
      b.textContent=count;
      b.setAttribute('aria-label',`${count} jogadores`);
      b.onclick=()=>choosePlayerCount(Number(count));
      controls.appendChild(b);
    });
    try{
      const saved=Number(localStorage.getItem('pokercoach.playerCount'));
      if(positionOrder[saved]) playerCount=saved;
    }catch(e){}
    renderTable();
    $('.analyze-btn').disabled=false;
    scheduleAnalysis();
  }catch(e){
    $('#tableHint').textContent='Não foi possível carregar a mesa. Atualize a página.';
  }
}

$$('.choice').forEach(b=>b.onclick=()=>{
  $$(`.choice[data-field="${b.dataset.field}"]`).forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  $('#reviewForm').elements[b.dataset.field].value=b.dataset.value;
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

$$('.action-choice').forEach(b=>b.onclick=()=>{
  $$('.action-choice').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  $('#reviewForm').elements.situation.value=b.dataset.value;
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

$$('.post-action').forEach(b=>b.onclick=()=>{
  $$('.post-action').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  $('#reviewForm').elements.post_action.value=b.dataset.value;
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

function toggleInputs(selector,shown){
  const node=$(selector);
  if(!node) return;
  node.hidden=!shown;
  node.querySelectorAll('input,select').forEach(i=>i.disabled=!shown);
}

function boardCount(){
  const f=$('#reviewForm').elements;
  return boardFields.filter(k=>f[k].value).length;
}

function updateStreet(){
  const f=$('#reviewForm').elements;
  const n=boardCount();
  let street='preflop';
  if(n===3) street='flop';
  else if(n===4) street='turn';
  else if(n===5) street='river';
  f.street.value=street;

  const labels={preflop:'PRÉ-FLOP',flop:'FLOP',turn:'TURN',river:'RIVER'};
  $('#streetReadout').textContent=(n===1||n===2)?'COMPLETE O FLOP':labels[street];
  $('#postStreetName').textContent=labels[street]||'FLOP';

  const slots=$$('.board-slot');
  slots.forEach((b,i)=>{
    if(i<3) b.disabled=false;
    else if(i===3) b.disabled=n<3;
    else b.disabled=n<4;
  });
  syncContext();
}

function syncContext(){
  const f=$('#reviewForm').elements;
  const n=boardCount();
  const postflop=n>=3;
  $('#preflopContext').hidden=postflop;
  $('#postflopContext').hidden=!postflop;

  toggleInputs('#raiseInputs',!postflop && f.situation.value==='facing_raise');
  toggleInputs('#tournamentContext',f.mode.value==='tournament');

  const facingBet=postflop && f.post_action.value==='facing_bet';
  const call=$('#callAmount');
  call.hidden=!facingBet;
  f.call_bb.disabled=!facingBet;
  if(!facingBet) f.call_bb.value=0;

  if(!positionOrder[playerCount]) return;
  const positions=positionOrder[playerCount];
  const order=playerCount===2?positions:[...positions.slice(3),...positions.slice(0,3)];
  const previous=f.opener_position.value;
  const heroIndex=order.indexOf(f.position.value);
  const options=heroIndex>=0?order.slice(0,heroIndex):[];
  f.opener_position.innerHTML='<option value="">Selecione a posição</option>'+
    options.map(p=>`<option value="${p}">${p}</option>`).join('');
  if(options.includes(previous)) f.opener_position.value=previous;
}

$('#reviewForm').addEventListener('input',e=>{
  if(e.target.matches('input,select')){
    invalidateReview();
    scheduleAnalysis();
  }
});

$('#reviewForm').addEventListener('change',()=>{
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

$('#advancedToggle').onclick=()=>{
  const a=$('#advanced');
  a.hidden=!a.hidden;
  $('#advancedToggle span').textContent=a.hidden?'⌄':'⌃';
};

function selectedCards(exceptSlot=null){
  const f=$('#reviewForm').elements;
  return ['card1','card2',...boardFields]
    .filter(k=>k!==exceptSlot)
    .map(k=>f[k].value)
    .filter(Boolean);
}

function slotLabel(slot){
  return {
    card1:'Sua carta 1',card2:'Sua carta 2',
    flop1:'Flop 1',flop2:'Flop 2',flop3:'Flop 3',
    turn:'Turn',river:'River'
  }[slot]||'Carta';
}

function renderCardSlot(slot){
  const f=$('#reviewForm').elements;
  const value=f[slot].value;
  const btn=$(`[data-slot="${slot}"]`);
  if(!btn) return;

  const isBoard=boardFields.includes(slot);
  if(!value){
    btn.className=(isBoard?'board-slot':'card-slot')+
      (slot==='turn'?' turn-slot':'')+(slot==='river'?' river-slot':'');
    btn.innerHTML=`<span>+</span><small>${isBoard?(slot.startsWith('flop')?'FLOP':slot.toUpperCase()):(slot==='card1'?'Carta 1':'Carta 2')}</small>`;
    return;
  }
  const rank=value[0];
  const suit=value[1];
  const suitRow=suitData.find(x=>x[0]===suit);
  const [,,color]=suitRow;
  const symbol=suitRow[1];
  btn.className=(isBoard?'board-slot':'card-slot')+
    ` selected ${color}`+(slot==='turn'?' turn-slot':'')+(slot==='river'?' river-slot':'');
  btn.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;
}

function showSuitStep(){
  selectedSuit=null;
  $('#pickerTitle').textContent='1. Escolha o naipe';
  $('#suitStep').hidden=false;
  $('#rankStep').hidden=true;
  const box=$('#suitChoices');
  box.innerHTML='';
  suitData.forEach(([code,symbol,color,name])=>{
    const b=document.createElement('button');
    b.type='button';
    b.className=`suit-choice ${color}`;
    b.innerHTML=`<span>${symbol}</span><b>${name}</b>`;
    b.onclick=()=>showRankStep(code,symbol,color,name);
    box.appendChild(b);
  });
}

function showRankStep(code,symbol,color,name){
  selectedSuit={code,symbol,color,name};
  $('#pickerTitle').textContent='2. Escolha a carta';
  $('#suitStep').hidden=true;
  $('#rankStep').hidden=false;
  const used=new Set(selectedCards(activeCardSlot));
  const box=$('#rankChoices');
  box.innerHTML='';
  ranks.forEach(rank=>{
    const card=rank+code;
    const b=document.createElement('button');
    b.type='button';
    b.className=`rank-choice ${color}`;
    b.disabled=used.has(card);
    b.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;
    b.onclick=()=>selectCard(card);
    box.appendChild(b);
  });
}

function openPicker(slot){
  const btn=$(`[data-slot="${slot}"]`);
  if(btn?.disabled) return;
  activeCardSlot=slot;
  $('#pickerLabel').textContent=slotLabel(slot);
  showSuitStep();
  $('#cardPicker').hidden=false;
}

function selectCard(card){
  invalidateReview();
  $('#reviewForm').elements[activeCardSlot].value=card;
  renderCardSlot(activeCardSlot);
  $('#cardPicker').hidden=true;
  updateStreet();
  scheduleAnalysis();
}

$$('.card-slot,.board-slot').forEach(b=>b.onclick=()=>openPicker(b.dataset.slot));
$('#backToSuit').onclick=showSuitStep;
$('#closePicker').onclick=()=>$('#cardPicker').hidden=true;
$('#cardPicker').onclick=e=>{if(e.target.id==='cardPicker') e.currentTarget.hidden=true};

$('#clearBoard').onclick=()=>{
  const f=$('#reviewForm').elements;
  boardFields.forEach(k=>{f[k].value='';renderCardSlot(k)});
  invalidateReview('Board limpo. Voltamos ao pré-flop.');
  updateStreet();
  scheduleAnalysis();
};

function readiness(){
  const f=$('#reviewForm').elements;
  if(!f.card1.value||!f.card2.value)
    return 'Escolha suas duas cartas.';
  const n=boardCount();
  if(n===1||n===2)
    return 'Complete as três cartas do flop.';
  if(f.street.value==='preflop'&&f.situation.value==='facing_raise'&&!f.opener_position.value)
    return 'Selecione quem fez o primeiro aumento.';
  if(f.street.value!=='preflop'){
    if(Number(f.pot_bb.value)<=0) return 'Informe o pote atual.';
    if(f.post_action.value==='facing_bet'&&Number(f.call_bb.value)<=0)
      return 'Informe quanto falta pagar.';
  }
  return '';
}

function buildPayload(){
  const f=$('#reviewForm').elements;
  const data=formData($('#reviewForm'));
  data.completed_hand=true;
  data.icm_pressure=f.icm_context?.value==='pressure';
  data.call_bb=f.post_action?.value==='facing_bet'?Number(f.call_bb.value||0):0;
  data.record_review=false;
  return data;
}

function rangeGrid(r){
  if(!r.range_hands?.length) return '';
  const included=new Set(r.range_hands);
  let cells='';
  ranks.forEach((a,i)=>ranks.forEach((b,j)=>{
    const hand=i===j?a+b:i<j?a+b+'s':b+a+'o';
    cells+=`<span class="range-cell ${included.has(hand)?'included':''} ${hand===r.hand?'selected-hand':''}" title="${hand}: ${included.has(hand)?'no conjunto da fonte':'fora do conjunto'}">${hand}</span>`;
  }));
  return `<details class="range-details"><summary>Ver range gráfico</summary><div class="range-grid">${cells}</div><p class="range-notation">${escapeHTML(r.range)}</p></details>`;
}

function renderResult(r){
  const box=$('#result');
  const sources=(r.sources||[]).map(s=>
    `<a href="${escapeHTML(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(s.title)}</a>`
  ).join(' · ');

  const board=r.board_text? `<p class="board-result"><b>Board:</b> ${escapeHTML(r.board_text)} · ${escapeHTML(r.hand_class||'')} · ${escapeHTML(r.board_texture||'')}</p>`:'';
  const bet=r.bet_bb!=null?` · <b>${Number(r.bet_bb).toFixed(2)} BB</b>`:'';
  box.innerHTML=`
    <div class="decision ${escapeHTML(String(r.action).toLowerCase().replaceAll(' ','-'))}">${escapeHTML(r.action)}</div>
    <h2>${escapeHTML(r.hand)} · ${escapeHTML(r.sizing)}${bet}</h2>
    ${board}
    <p><b>${escapeHTML(r.profile)}</b></p>
    <p>Mesa de ${r.player_count} · ${escapeHTML(r.position)}${r.study_stack_bb!=null?` · estudo-base ${r.study_stack_bb} BB`:''}</p>
    <ul>${(r.notes||[]).map(n=>`<li>${escapeHTML(n)}</li>`).join('')}</ul>
    ${rangeGrid(r)}
    <p class="source-links">${sources}</p>
    <small>${escapeHTML(r.disclaimer)}</small>`;
  box.hidden=false;
  $('#autoStatus').innerHTML=`Decisão atual: <b>${escapeHTML(r.action)}</b>`;
}

async function runAnalysis(scroll=false){
  clearTimeout(autoTimer);
  const missing=readiness();
  if(missing){
    $('#autoStatus').textContent=missing;
    $('#result').hidden=true;
    return;
  }

  const revision=++reviewRevision;
  $('.analyze-btn').disabled=true;
  $('#autoStatus').textContent='Calculando…';
  try{
    const r=await api('/api/analyze',buildPayload());
    if(revision!==reviewRevision) return;
    renderResult(r);
    if(scroll) $('#result').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){
    if(revision===reviewRevision){
      $('#result').hidden=false;
      $('#result').innerHTML=`<p class="error">${escapeHTML(err.message)}</p>`;
      $('#autoStatus').textContent='Falta corrigir uma informação.';
    }
  }finally{
    $('.analyze-btn').disabled=false;
  }
}

function scheduleAnalysis(){
  clearTimeout(autoTimer);
  autoTimer=setTimeout(()=>runAnalysis(false),350);
}

$('#reviewForm').onsubmit=e=>{
  e.preventDefault();
  runAnalysis(true);
};

$('#sessionForm').onsubmit=async e=>{
  e.preventDefault();
  try{
    await api('/api/session',formData(e.target));
    e.target.reset();
    e.target.played_at.value=new Date().toISOString().slice(0,10);
    loadSummary();
  }catch(err){alert(err.message)}
};

async function loadSummary(){
  try{
    const s=await api('/api/summary');
    $('#summary').innerHTML=`<div class="kpis"><div><b>${s.sessions}</b><span>Sessões</span></div><div><b>${Number(s.profit).toFixed(2)}</b><span>Resultado</span></div><div><b>${Number(s.invested).toFixed(2)}</b><span>Total entradas</span></div></div><h3>Últimas sessões</h3>${s.recent.length?`<div class="table"><table><tr><th>Data</th><th>Modo</th><th>Limite</th><th>Entrada</th><th>Saída</th></tr>${s.recent.map(x=>`<tr><td>${x[0]}</td><td>${x[1]}</td><td>${x[2]}</td><td>${x[3]}</td><td>${x[4]}</td></tr>`).join('')}</table></div>`:'<p>Nenhuma sessão registrada.</p>'}`;
  }catch(e){}
}

$('#sessionForm').played_at.value=new Date().toISOString().slice(0,10);
['card1','card2',...boardFields].forEach(renderCardSlot);
updateStreet();
initTable();
