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
let visionEnabled=true;
let visionTimer=null;
let visionLastSignature='';
let visionLastNumericSignature='';
const VISION_URL='/api/vision/state';

const ACTION_LABELS={
  'FOLD':'DESISTIR',
  'CHECK':'PASSAR',
  'CALL':'PAGAR',
  'BET':'APOSTAR',
  'RAISE':'AUMENTAR',
  'ALL-IN':'ALL-IN',
  'SEM AÇÃO':'SEM AÇÃO',
  'SEM COBERTURA':'SEM COBERTURA'
};

function actionLabel(action){
  return ACTION_LABELS[action]||action||'';
}

const boardFields=['flop1','flop2','flop3','turn','river'];
const suitData=[
  ['S','♠','black','Espadas'],
  ['H','♥','red','Copas'],
  ['D','♦','red','Ouros'],
  ['C','♣','black','Paus']
];
const ranks=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];

const POSITION_COLORS={
  'UTG':'#ff5c5c',
  'UTG+1':'#ff8a3d',
  'UTG+2':'#ffd166',
  'MP':'#b7e548',
  'LJ':'#40d98a',
  'HJ':'#22d3ee',
  'CO':'#4ea5ff',
  'BTN':'#a78bfa',
  'BTN/SB':'#d96bff',
  'SB':'#ff6fb5',
  'BB':'#e2e8f0'
};

function positionColor(position){
  return POSITION_COLORS[position]||'#9bb5aa';
}

function applyPositionColor(node,position){
  if(!node) return;
  node.dataset.position=position||'';
  node.style.setProperty('--pos-color',positionColor(position));
}

function positionTag(position){
  const safe=escapeHTML(position||'');
  const color=positionColor(position);
  return `<span class="position-tag" style="--pos-color:${color}">${safe}</span>`;
}

function renderPositionLegend(){
  const box=$('#positionLegend');
  if(!box || !positionOrder[playerCount]) return;
  box.innerHTML=positionOrder[playerCount]
    .map(pos=>`<span class="position-legend-item" style="--pos-color:${positionColor(pos)}"><i></i>${escapeHTML(pos)}</span>`)
    .join('');
}

function invalidateReview(message='Atualizando decisão…'){
  reviewRevision++;
  $('#autoStatus').textContent=message;
}

const SEAT_LAYOUTS={
  2:[[50,88],[50,11]],
  3:[[50,88],[16,28],[84,28]],
  4:[[50,88],[10,50],[50,10],[90,50]],
  5:[[50,88],[13,66],[18,20],[82,20],[87,66]],
  6:[[50,88],[13,68],[12,29],[50,10],[88,29],[87,68]],
  7:[[50,88],[16,72],[9,43],[22,16],[78,16],[91,43],[84,72]],
  8:[[50,88],[16,72],[8,45],[18,18],[50,9],[82,18],[92,45],[84,72]],
  9:[[50,88],[18,73],[8,49],[13,24],[34,10],[66,10],[87,24],[92,49],[82,73]],
  10:[[50,88],[20,75],[8,56],[9,31],[26,13],[50,8],[74,13],[91,31],[92,56],[80,75]]
};

function seatLayout(count){
  return SEAT_LAYOUTS[count]||SEAT_LAYOUTS[8];
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
    applyPositionColor(b,pos);
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
  applyPositionColor($('#heroPosition'),heroPos);
  applyPositionColor($('.position-readout'),heroPos);
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
  renderPositionLegend();
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

const betToggle=$('#betToggle');
if(betToggle) betToggle.onclick=()=>{
  const f=$('#reviewForm').elements;
  const betting=f.post_action.value!=='facing_bet';
  f.post_action.value=betting?'facing_bet':'checked_to_hero';
  if(!betting){
    f.bet_pressure.value='none';
    $('.pressure-choice').forEach(x=>x.classList.remove('active'));
  }
  betToggle.classList.toggle('active',betting);
  $('#betPressure').hidden=!betting;
  invalidateReview();
  syncContext();
  scheduleAnalysis();
};

$('.pressure-choice').forEach(b=>b.onclick=()=>{
  const f=$('#reviewForm').elements;
  $('.pressure-choice').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  f.post_action.value='facing_bet';
  f.bet_pressure.value=b.dataset.value;
  if(betToggle) betToggle.classList.add('active');
  $('#betPressure').hidden=false;
  invalidateReview();
  scheduleAnalysis();
});

$$('.quick-value').forEach(b=>b.onclick=()=>{
  const input=$('#reviewForm').elements[b.dataset.target];
  if(!input) return;
  input.value=b.dataset.value;
  $$(`.quick-value[data-target="${b.dataset.target}"]`).forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
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

  const facingBet=postflop && f.post_action.value==='facing_bet';
  if($('#betPressure')) $('#betPressure').hidden=!facingBet;
  if($('#betToggle')) $('#betToggle').classList.toggle('active',facingBet);
  if(!facingBet){
    f.bet_pressure.value='none';
    f.call_bb.value=0;
  }

  if(!positionOrder[playerCount]) return;
  const positions=positionOrder[playerCount];
  const order=playerCount===2?positions:[...positions.slice(3),...positions.slice(0,3)];
  const previous=f.opener_position.value;
  const heroIndex=order.indexOf(f.position.value);
  const options=heroIndex>=0?order.slice(0,heroIndex):[];
  f.opener_position.innerHTML='<option value="">Selecione a posição</option>'+
    options.map(p=>`<option value="${p}" style="color:${positionColor(p)}">● ${p}</option>`).join('');
  if(options.includes(previous)) f.opener_position.value=previous;
  const opener=f.opener_position.value;
  applyPositionColor(f.opener_position,opener);
  f.opener_position.classList.toggle('position-selected',Boolean(opener));
}

$('#reviewForm').addEventListener('input',e=>{
  if(e.target.matches('input,select')){
    invalidateReview();
    scheduleAnalysis();
  }
});

$('#reviewForm').addEventListener('change',e=>{
  invalidateReview();
  if(e.target?.name==='opener_position'){
    applyPositionColor(e.target,e.target.value);
    e.target.classList.toggle('position-selected',Boolean(e.target.value));
  }
  syncContext();
  scheduleAnalysis();
});

if($('#advancedToggle')) $('#advancedToggle').onclick=()=>{
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
  btn.innerHTML=`<b>${displayRank(rank)}</b><span>${symbol}</span>`;
}

function displayRank(rank){
  return rank==='T'?'10':rank;
}

function renderFastDeck(){
  const used=new Set(selectedCards(activeCardSlot));
  const box=$('#fastDeck');
  box.innerHTML='';
  suitData.forEach(([code,symbol,color,name])=>{
    const group=document.createElement('section');
    group.className='fast-deck-suit';
    const title=document.createElement('div');
    title.className=`fast-suit-label ${color}`;
    title.innerHTML=`<span>${symbol}</span><b>${name}</b>`;
    const cards=document.createElement('div');
    cards.className='fast-cards';
    ranks.forEach(rank=>{
      const card=rank+code;
      const b=document.createElement('button');
      b.type='button';
      b.className=`fast-card ${color}`;
      b.disabled=used.has(card);
      b.setAttribute('aria-label',`${displayRank(rank)} de ${name}`);
      b.innerHTML=`<b>${displayRank(rank)}</b><span>${symbol}</span>`;
      b.onclick=()=>selectCard(card);
      cards.appendChild(b);
    });
    group.append(title,cards);
    box.appendChild(group);
  });
}

function openPicker(slot){
  const btn=$(`[data-slot="${slot}"]`);
  if(btn?.disabled) return;
  activeCardSlot=slot;
  $('#pickerTitle').textContent='Escolha a carta';
  $('#pickerLabel').textContent=slotLabel(slot);
  renderFastDeck();
  $('#cardPicker').hidden=false;
}

function selectCard(card){
  invalidateReview();
  const f=$('#reviewForm').elements;
  const current=activeCardSlot;
  f[current].value=card;
  renderCardSlot(current);
  updateStreet();

  const quickNext={card1:'card2',flop1:'flop2',flop2:'flop3'};
  const next=quickNext[current];
  if(next && !f[next].value){
    activeCardSlot=next;
    $('#pickerLabel').textContent=slotLabel(next);
    renderFastDeck();
  }else{
    $('#cardPicker').hidden=true;
  }
  scheduleAnalysis();
}

$$('.card-slot,.board-slot').forEach(b=>b.onclick=()=>openPicker(b.dataset.slot));
$('#closePicker').onclick=()=>$('#cardPicker').hidden=true;
$('#cardPicker').onclick=e=>{if(e.target.id==='cardPicker') e.currentTarget.hidden=true};

$('#clearBoard').onclick=()=>{
  const f=$('#reviewForm').elements;
  boardFields.forEach(k=>{f[k].value='';renderCardSlot(k)});
  invalidateReview('Board limpo. Voltamos ao pré-flop.');
  updateStreet();
  scheduleAnalysis();
};

function validVisionCard(card){
  return typeof card==='string' && /^[AKQJT2-9][SHDC]$/.test(card);
}

function setVisionBar(kind,message){
  const bar=$('#visionBar');
  if(!bar) return;
  bar.classList.remove('connected','waiting','disconnected','paused');
  bar.classList.add(kind);
  $('#visionStatus').textContent=message;
}

function setVisionEnabled(enabled){
  visionEnabled=Boolean(enabled);
  const button=$('#visionToggle');
  if(button) button.textContent=visionEnabled?'Automático ON':'Automático OFF';
  try{localStorage.setItem('pokercoach.visionEnabled',visionEnabled?'1':'0')}catch(e){}
  if(!visionEnabled) setVisionBar('paused','Leitura visual pausada · seleção manual ativa');
}

function applyVisionNumericState(state){
  if(!visionEnabled || !state?.running) return;

  const f=$('#reviewForm').elements;
  const heroBB=Number(state?.hero_stack_bb||0);
  const potBB=Number(state?.pot_bb||0);
  const signature=JSON.stringify([heroBB||null,potBB||null]);

  const metrics=[];
  if(heroBB>0) metrics.push(`Meu stack ${heroBB.toFixed(1)} BB`);
  if(potBB>0) metrics.push(`Pote ${potBB.toFixed(2)} BB`);

  const meter=$('#visionNumbers');
  if(meter){
    meter.textContent=metrics.length?metrics.join(' · '):'Aguardando MEU STACK e POTE…';
    meter.classList.toggle('ready',metrics.length>0);
  }

  if(signature===visionLastNumericSignature) return;
  visionLastNumericSignature=signature;

  let changed=false;
  if(heroBB>0 && Math.abs(Number(f.stack_bb.value||0)-heroBB)>0.01){
    f.stack_bb.value=heroBB.toFixed(2);
    changed=true;
  }
  if(potBB>0 && Math.abs(Number(f.pot_bb.value||0)-potBB)>0.01){
    f.pot_bb.value=potBB.toFixed(2);
    changed=true;
  }

  if(changed){
    invalidateReview('PokerVision: stack/pote atualizados');
    syncContext();
    scheduleAnalysis();
  }
}

function applyVisionState(state){
  if(!visionEnabled || !state?.running || !state?.confirmed) return;

  const hand=Array.isArray(state.hand)?state.hand:[];
  const board=Array.isArray(state.board)?state.board:[];
  if(!([0,2].includes(hand.length) && [0,3,4,5].includes(board.length))) return;
  if(!hand.every(validVisionCard) || !board.every(validVisionCard)) return;

  const all=[...hand,...board];
  if(new Set(all).size!==all.length) return;

  const signature=JSON.stringify([hand,board]);
  if(signature===visionLastSignature) return;
  visionLastSignature=signature;

  const f=$('#reviewForm').elements;
  const desired={
    card1:hand[0]||'',
    card2:hand[1]||'',
    flop1:board[0]||'',
    flop2:board[1]||'',
    flop3:board[2]||'',
    turn:board[3]||'',
    river:board[4]||''
  };

  let changed=false;
  Object.entries(desired).forEach(([slot,value])=>{
    if(f[slot].value!==value){
      f[slot].value=value;
      renderCardSlot(slot);
      changed=true;
    }
  });

  if(changed){
    invalidateReview(`PokerVision: ${state.street||'cartas atualizadas'}`);
    updateStreet();
    scheduleAnalysis();
  }
}

async function pollPokerVision(){
  clearTimeout(visionTimer);
  try{
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),700);
    const response=await fetch(VISION_URL,{
      method:'GET',
      cache:'no-store',
      credentials:'same-origin',
      signal:controller.signal
    });
    clearTimeout(timeout);
    if(!response.ok) throw new Error('bridge indisponível');
    const state=await response.json();

    if(state.connected && state.running && visionEnabled){
      applyVisionNumericState(state);
    }

    if(!state.connected){
      setVisionBar('disconnected','PokerVision ainda não enviou dados ao Beelink');
    }else if(!visionEnabled){
      setVisionBar('paused','PokerVision conectado · automático pausado');
    }else if(!state.running){
      setVisionBar('waiting','PokerVision conectado ao Beelink · clique em Iniciar monitoramento');
    }else if(!state.confirmed){
      setVisionBar('waiting','PokerVision conectado · confirmando leitura…');
    }else{
      const hand=(state.hand||[]).length?state.hand.join(' '):'sem mão';
      setVisionBar('connected',`PokerVision → Beelink OK · ${state.street||''} · ${hand}`);
      applyVisionState(state);
    }
  }catch(e){
    if(visionEnabled) setVisionBar('disconnected','Sem sincronização com PokerVision · manual disponível');
  }finally{
    visionTimer=setTimeout(pollPokerVision,500);
  }
}

function initPokerVision(){
  try{
    const saved=localStorage.getItem('pokercoach.visionEnabled');
    if(saved!==null) visionEnabled=saved!=='0';
  }catch(e){}
  setVisionEnabled(visionEnabled);
  $('#visionToggle').onclick=()=>{
    setVisionEnabled(!visionEnabled);
    if(visionEnabled){
      visionLastSignature='';
      pollPokerVision();
    }
  };
  pollPokerVision();
}

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
    if(Number(f.pot_bb.value)<=0) return 'Aguardando leitura do pote.';
    if(f.post_action.value==='facing_bet'&&(!f.bet_pressure.value||f.bet_pressure.value==='none'))
      return 'Escolha BAIXA, MÉDIA, ALTA ou ALL-IN.';
  }
  return '';
}

function buildPayload(){
  const f=$('#reviewForm').elements;
  const data=formData($('#reviewForm'));
  data.completed_hand=true;
  data.icm_pressure=false;
  data.call_bb=0;
  data.bet_pressure=f.post_action?.value==='facing_bet'?(f.bet_pressure.value||'none'):'none';
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
  const label=actionLabel(r.action);
  const uncovered=r.action==='SEM COBERTURA';
  box.innerHTML=`
    <div class="decision ${escapeHTML(String(r.action).toLowerCase().replaceAll(' ','-'))}">${escapeHTML(label)}</div>
    ${uncovered?'<div class="coverage-warning">O motor ainda não possui range suficiente para transformar este cenário em DESISTIR / PAGAR / AUMENTAR sem inventar uma estratégia.</div>':''}
    <h2>${escapeHTML(r.hand)} · ${escapeHTML(r.sizing)}${bet}</h2>
    ${board}
    <p><b>${escapeHTML(r.profile)}</b></p>
    <p>Mesa de ${r.player_count} · ${positionTag(r.position)}${r.study_stack_bb!=null?` · estudo-base ${r.study_stack_bb} BB`:''}</p>
    <ul>${(r.notes||[]).map(n=>`<li>${escapeHTML(n)}</li>`).join('')}</ul>
    ${rangeGrid(r)}
    <p class="source-links">${sources}</p>
    <small>${escapeHTML(r.disclaimer)}</small>`;
  box.hidden=false;
  $('#autoStatus').innerHTML=`Decisão atual: <b>${escapeHTML(actionLabel(r.action))}</b>`;
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
initPokerVision();
