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
let tableMaxSeats=9;
let gameType='cash';
let dealerSeat=0;
let activeCardSlot='card1';
let visionEnabled=true;
let visionTimer=null;
let visionLastSignature='';
let visionLastNumericSignature='';
let visionPendingPlayerCount=null;
let visionPendingInactiveSeats=null;
let visionPendingMaxSeats=null;
let visionPendingConfirmedAt=0;
let visionTableState='disabled';
let visionInactivePoints=[];
let visionInactiveSeatIndices=[];
let visionSeatObservations=[];
let visionLastState=null;
let visionPlayerAutoEnabled=true;
let visionManualOverrideKey='';
let visionAutoLastSignature='';
let lastValidPositionState=null;
let lastStreet='preflop';
const VISION_URL='/api/vision/state';

const GAME_TYPES={
  cash:{
    mode:'cash',
    hint:'Cash game · sem ICM.'
  },
  sitngo:{
    mode:'tournament',
    hint:'Sit & Go · usa a base de torneio atual; ICM especializado ainda não está modelado.'
  },
  spin:{
    mode:'spin',
    hint:'Spin & Go · motor dedicado 3-handed → heads-up por stack efetivo.'
  },
  mtt:{
    mode:'tournament',
    hint:'Torneio MTT · usa a base de torneio atual; bolha/pay jumps ainda exigem modelagem de ICM.'
  }
};

const ACTION_LABELS={
  'FOLD':'DESISTIR',
  'CHECK':'PASSAR',
  'CALL':'PAGAR',
  'BET':'APOSTAR',
  'RAISE':'AUMENTAR',
  'ALL-IN':'ALL-IN',
  'LIMP':'LIMP',
  'MIXED':'MISTA',
  'ESTADO INVÁLIDO':'ESTADO INVÁLIDO',
  'SEM AÇÃO':'SEM AÇÃO',
  'SEM COBERTURA':'SEM COBERTURA'
};

function actionLabel(action){
  return ACTION_LABELS[action]||action||'';
}

function formatBB(value){
  const n=Number(value)||0;
  const rounded=Math.round(n*100)/100;
  return rounded.toLocaleString('pt-BR',{maximumFractionDigits:2});
}

function preflopPressureLabel(kind,stackValue){
  const stack=Math.max(0,Number(stackValue)||0);
  if(kind==='low') return '2–2,5 BB';
  if(kind==='medium') return '3–4 BB';
  if(kind==='high') return stack>4.5?`4,5–${formatBB(Math.max(4.5,stack-0.1))} BB`:'indisponível';
  if(kind==='allin') return stack>0?`${formatBB(stack)} BB`:'aguardando stack';
  return '—';
}

function preflopRepresentative(kind,stackValue){
  const stack=Math.max(0,Number(stackValue)||0);
  if(kind==='low') return Math.min(stack,2.25);
  if(kind==='medium') return Math.min(stack,3.5);
  if(kind==='high') return Math.min(stack,5);
  if(kind==='allin') return stack;
  return 0;
}

function postflopPressureRanges(potValue,stackValue){
  const pot=Math.max(0,Number(potValue)||0);
  const stack=Math.max(0,Number(stackValue)||0);
  if(pot<=0 || stack<=0) return null;

  const step=0.1;
  const clamp=(lo,hi)=>{
    const min=Math.round(lo*100)/100;
    const max=Math.round(Math.min(hi,stack-step)*100)/100;
    if(min>max || min>=stack) return null;
    return {min,max};
  };

  return {
    low:clamp(pot*.25,pot*.33),
    medium:clamp(pot*.50,pot*.67),
    high:clamp(pot*.75,pot*1.00),
    allin:{min:stack,max:stack}
  };
}

function postflopPressureLabel(kind,potValue,stackValue){
  const ranges=postflopPressureRanges(potValue,stackValue);
  if(!ranges) return 'aguardando pote/stack';
  const r=ranges[kind];
  if(!r) return 'indisponível';
  if(kind==='allin') return `${formatBB(r.min)} BB`;
  return `${formatBB(r.min)}–${formatBB(r.max)} BB`;
}

function updatePressureLabels(){
  const f=$('#reviewForm')?.elements;
  if(!f) return;
  const stack=Number(f.stack_bb.value||0);
  const pot=Number(f.pot_bb.value||0);

  $$('.pre-pressure-choice').forEach(button=>{
    const kind=button.dataset.value;
    const small=button.querySelector('small');
    if(small) small.textContent=preflopPressureLabel(kind,stack);
    button.disabled=kind==='high' && stack>0 && stack<=4.5;
  });

  const postRanges=postflopPressureRanges(pot,stack);
  $$('.pressure-choice').forEach(button=>{
    const kind=button.dataset.value;
    const small=button.querySelector('small');
    if(small) small.textContent=postflopPressureLabel(kind,pot,stack);
    button.disabled=kind!=='allin' && Boolean(postRanges) && !postRanges[kind];
  });

  const preSummary=$('#stackPressureSummary');
  if(preSummary){
    preSummary.textContent=stack>0
      ? `Pré-flop em BB · seu stack ${formatBB(stack)} BB`
      : 'Aguardando leitura do seu stack';
  }

  const postSummary=$('#postflopPressureSummary');
  if(postSummary){
    if(stack>0 && pot>0){
      const ratio=stack/pot;
      postSummary.textContent=
        `Pote ${formatBB(pot)} BB · stack ${formatBB(stack)} BB · stack/pote ${ratio.toFixed(2)}`;
    }else{
      postSummary.textContent='Aguardando leitura do pote e do stack';
    }
  }
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
  if(!box) return;
  const state=buildPhysicalPositionState();
  let positions=positionOrder?.[state.engineCount]||[];
  if(state.deadButton){
    positions=positions.filter(
      position=>position!=='BTN' && position!=='BTN/SB'
    );
  }
  if(!positions.length) positions=positionOrder?.[playerCount]||[];
  box.innerHTML=positions
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


function physicalSeatCount(){
  // Spin & Go usa mesa física de 3 lugares. Em treino manual heads-up,
  // sem um mapa fresco do PokerVision, mostramos apenas os dois jogadores.
  if(gameType==='spin'){
    if(playerCount===2 && !visionPhysicalSeatStateFresh()) return 2;
    return 3;
  }
  const count=Number(tableMaxSeats||playerCount||8);
  return SEAT_LAYOUTS[count]?count:8;
}

function inactivePhysicalSeats(){
  const count=physicalSeatCount();
  const inactive=new Set(
    (Array.isArray(visionInactiveSeatIndices)?visionInactiveSeatIndices:[])
      .map(Number)
      .filter(seat=>Number.isInteger(seat)&&seat>=0&&seat<count&&seat!==0)
  );
  return inactive;
}

function activePhysicalSeats(){
  const count=physicalSeatCount();
  const inactive=inactivePhysicalSeats();
  const seats=[];
  for(let seat=0;seat<count;seat++){
    if(!inactive.has(seat)) seats.push(seat);
  }
  return seats;
}

function visionPhysicalSeatStateFresh(){
  const scanAt=Number(visionLastState?.table_scan_at||0);
  const age=scanAt>0 ? Math.max(0,(Date.now()/1000)-scanAt) : Infinity;
  return Boolean(
    visionEnabled
    && visionTableState==='confirmed'
    && Number.isFinite(age)
    && age<=6
  );
}

function positionActiveSeats(){
  const active=activePhysicalSeats();

  // When PokerVision has a fresh confirmed physical-seat map, that map wins.
  // It must not be blocked by a stale player-count dropdown from the previous
  // hand/table state.
  if(
    visionPhysicalSeatStateFresh()
    && active.length>=2
    && active.length<=10
    && positionOrder?.[active.length]
  ){
    return active;
  }

  // Manual/basic mode keeps the previous behaviour when the selected count
  // already agrees with the physical active-seat map.
  if(active.length===playerCount && positionOrder?.[playerCount]){
    return active;
  }

  return null;
}

function buildPhysicalPositionState(){
  const physicalCount=physicalSeatCount();
  const active=positionActiveSeats();

  if(active){
    const activeCount=active.length;
    const deadButton=!active.includes(dealerSeat);
    const engineCount=(
      deadButton
      && activeCount<physicalCount
      && positionOrder?.[activeCount+1]
    )
      ? activeCount+1
      : activeCount;

    let positions=positionOrder?.[engineCount]||[];
    if(deadButton){
      positions=positions.filter(
        position=>position!=='BTN' && position!=='BTN/SB'
      );
    }

    if(positions.length===active.length){
      const ordered=[];
      const firstStep=deadButton?1:0;
      for(let step=firstStep;step<physicalCount+firstStep;step++){
        const seat=(dealerSeat+step)%physicalCount;
        if(active.includes(seat) && !ordered.includes(seat)){
          ordered.push(seat);
        }
      }

      if(ordered.length===active.length){
        const map=new Map();
        ordered.forEach((seat,index)=>{
          if(positions[index]) map.set(seat,positions[index]);
        });

        if(map.size===active.length){
          const state={
            physicalCount,
            dealerSeat,
            active:[...active],
            engineCount,
            deadButton,
            mapEntries:[...map.entries()],
            fallback:false,
          };
          lastValidPositionState=state;
          return {...state,map};
        }
      }
    }
  }

  // Never blank a valid position in the middle of a hand because one OCR
  // frame or a delayed count disagreed. Keep the last known-good map for the
  // same physical table/button until a new valid map is available.
  if(
    lastValidPositionState
    && lastValidPositionState.physicalCount===physicalCount
    && lastValidPositionState.dealerSeat===dealerSeat
  ){
    return {
      ...lastValidPositionState,
      map:new Map(lastValidPositionState.mapEntries),
      fallback:true,
    };
  }

  return {
    physicalCount,
    dealerSeat,
    active:[],
    engineCount:playerCount,
    deadButton:false,
    map:new Map(),
    mapEntries:[],
    fallback:true,
  };
}

function enginePlayerCountForButton(){
  return buildPhysicalPositionState().engineCount;
}

function physicalPositionMap(){
  return buildPhysicalPositionState().map;
}

function mapObservationsToCurrentSeats(observations,_count){
  const count=physicalSeatCount();
  const layout=seatLayout(count);
  const mapped=new Map();
  const source=(Array.isArray(observations)?observations:[])
    .filter(obs=>obs && obs.status!=='inactive');

  source.forEach(obs=>{
    const seat=Number(obs.seat_index);
    if(Number.isInteger(seat) && seat>=0 && seat<count){
      const previous=mapped.get(seat);
      if(!previous || (previous.stale && !obs.stale)){
        mapped.set(seat,obs);
      }
      return;
    }

    const ox=Number(obs.x)*100;
    const oy=Number(obs.y)*100;
    if(!Number.isFinite(ox)||!Number.isFinite(oy)) return;
    let bestSeat=-1;
    let bestDistance=Infinity;
    layout.forEach(([x,y],candidate)=>{
      const dx=(x-ox)/100;
      const dy=(y-oy)/100;
      const distance=dx*dx+dy*dy;
      if(distance<bestDistance){
        bestDistance=distance;
        bestSeat=candidate;
      }
    });
    if(bestSeat>=0 && bestDistance<=0.075){
      const previous=mapped.get(bestSeat);
      if(!previous || (previous.stale && !obs.stale)){
        mapped.set(bestSeat,obs);
      }
    }
  });
  return mapped;
}

function mapPointsToLayout(points,count){
  const layout=seatLayout(count);
  const used=new Set();
  (Array.isArray(points)?points:[]).forEach(point=>{
    if(!Array.isArray(point)||point.length!==2) return;
    const px=Number(point[0])*100;
    const py=Number(point[1])*100;
    let best=-1;
    let bestDistance=Infinity;
    layout.forEach(([x,y],i)=>{
      if(used.has(i)) return;
      const dx=(x-px)/100;
      const dy=(y-py)/100;
      const distance=dx*dx+dy*dy;
      if(distance<bestDistance){
        bestDistance=distance;
        best=i;
      }
    });
    if(best>=0 && bestDistance<=0.095) used.add(best);
  });
  return used;
}

function renderVisionPlayerDetails(){ return; }

function stackReadingIsStable(obs){
  if(!obs || !Number.isFinite(Number(obs.stack_bb))) return false;
  if(!obs.stale && obs.data_state!=='stale') return true;
  const age=Number(obs.last_seen_age||0);
  // PokerStars dims/flashes a player's plaque while action is on them.
  // Short OCR misses must not turn a reliable seat yellow.
  return Number.isFinite(age) && age<=6;
}

function stackReadingIsOld(obs){
  if(!obs || !Number.isFinite(Number(obs.stack_bb))) return false;
  return !stackReadingIsStable(obs);
}

function renderVisionHealthOverlay(){
  const layer=$('#visionSeatHealth');
  if(!layer) return;
  layer.innerHTML='';

  const count=physicalSeatCount();
  const inactive=inactivePhysicalSeats();
  const mapped=mapObservationsToCurrentSeats(visionSeatObservations,count);
  const tableError=visionTableState==='error';

  seatLayout(count).forEach(([x,y],i)=>{
    const dot=document.createElement('span');
    const obs=mapped.get(i);
    const heroStack=Number(visionLastState?.hero_stack_bb);
    const isInactive=inactive.has(i);
    const hasStack=i===0
      ? Number.isFinite(heroStack) && heroStack>0
      : obs && Number.isFinite(Number(obs.stack_bb));
    const stableStack=i===0
      ? hasStack
      : stackReadingIsStable(obs);
    const oldStack=i===0
      ? false
      : stackReadingIsOld(obs);

    let health='partial';
    let title='Stack ainda não lido';
    if(isInactive){
      health='absent';
      title='Ausente / lugar vazio';
    }else if(tableError){
      health='error';
      title='Erro na leitura da mesa';
    }else if(hasStack && stableStack){
      health='ok';
      const shownStack=i===0?heroStack:Number(obs?.stack_bb);
      title=`Stack ${formatBB(shownStack)} BB`;
    }else if(hasStack && oldStack){
      const shownStack=i===0?heroStack:Number(obs?.stack_bb);
      title=`Stack ${formatBB(shownStack)} BB · leitura antiga`;
    }

    dot.className=`vision-seat-dot ${health}`;
    dot.style.left=x+'%';
    dot.style.top=y+'%';
    dot.title=title;
    layer.appendChild(dot);
  });
}

function renderTable(){
  if(!positionOrder) return;

  const positionState=buildPhysicalPositionState();
  const physicalCount=physicalSeatCount();
  const inactive=inactivePhysicalSeats();
  const positions=positionState.map;
  const mappedStacks=mapObservationsToCurrentSeats(
    visionSeatObservations,
    physicalCount
  );
  const seats=$('#seats');
  seats.innerHTML='';
  $('#pokerTable').dataset.players=physicalCount;

  seatLayout(physicalCount).forEach(([x,y],i)=>{
    const isInactive=inactive.has(i);
    const pos=positions.get(i)||'';
    const b=document.createElement('button');
    b.type='button';
    b.className='seat'
      +(i===0?' hero':'')
      +(i===dealerSeat?' dealer':'')
      +(isInactive?' inactive':'');
    applyPositionColor(b,isInactive?'':pos);
    b.style.left=x+'%';
    b.style.top=y+'%';

    const stackObs=mappedStacks.get(i);
    const heroStack=Number(
      visionLastState?.hero_stack_bb
      ?? $('#reviewForm')?.elements?.stack_bb?.value
    );
    let stackText='';
    if(i===0 && Number.isFinite(heroStack) && heroStack>0){
      stackText=`<span class="seat-stack">${formatBB(heroStack)} BB</span>`;
    }else if(!isInactive && i!==0 && stackObs && Number.isFinite(Number(stackObs.stack_bb))){
      stackText=`<span class="seat-stack${stackReadingIsOld(stackObs)?' stale':''}">${formatBB(stackObs.stack_bb)} BB</span>`;
    }

    const seatLabel=isInactive?'AUSENTE':(pos||'—');
    b.innerHTML=`<span class="avatar">${i===0?'VOCÊ':(isInactive?'×':'♟')}</span><b>${seatLabel}</b>${stackText}${i===dealerSeat?'<i>D</i>':''}`;
    b.setAttribute(
      'aria-label',
      isInactive
        ? `Assento ${i+1}, ausente ou vazio. Clique se o botão real estiver neste lugar`
        : `${i===0?'Você':`Assento ${i+1}`}, ${pos||'posição aguardando'}. Colocar botão aqui`
    );
    b.setAttribute('aria-pressed',String(i===dealerSeat));

    b.onclick=()=>{
      dealerSeat=i;
      invalidateReview();
      renderTable();
      scheduleAnalysis();
    };
    seats.appendChild(b);
  });

  const heroPos=positions.get(0)||'';
  if(heroPos){
    $('#heroPosition').textContent=heroPos;
    applyPositionColor($('#heroPosition'),heroPos);
    applyPositionColor($('.position-readout'),heroPos);
    $('#reviewForm').elements.position.value=heroPos;
  }else{
    const previous=$('#reviewForm').elements.position.value;
    if(previous){
      $('#heroPosition').textContent=previous;
      applyPositionColor($('#heroPosition'),previous);
      applyPositionColor($('.position-readout'),previous);
    }else{
      $('#heroPosition').textContent='—';
      applyPositionColor($('#heroPosition'),'');
      applyPositionColor($('.position-readout'),'');
    }
  }

  const activeSeats=positionState.active;
  const engineCount=positionState.engineCount;
  $('#reviewForm').elements.player_count.value=engineCount;
  const reliable=positions.size>=2 && activeSeats.length===positions.size;
  $('#tableHint').textContent=reliable
    ? positionState.fallback
      ? `Leitura da mesa oscilou · mantendo o último mapa válido de posições.`
      : positionState.deadButton
      ? `Botão em assento ausente · posições calculadas como botão morto · ${activeSeats.length} jogadores ativos.`
      : `Mesa física de ${physicalCount} lugares · ${activeSeats.length} jogadores ativos. Clique no mesmo lugar do botão real.`
    : `Modo básico ativo · mantendo a última posição válida enquanto a mesa é confirmada.`;

  const playerSelect=$('#playerCountSelect');
  if(playerSelect) playerSelect.value=String(playerCount);
  renderPositionLegend();
  renderVisionHealthOverlay();
  syncContext();
}

function selectGameType(value){
  const cfg=GAME_TYPES[value]||GAME_TYPES.cash;
  gameType=GAME_TYPES[value]?value:'cash';
  const f=$('#reviewForm').elements;
  f.game_type.value=gameType;
  f.mode.value=cfg.mode;
  const select=$('#gameTypeSelect');
  if(select && select.value!==gameType) select.value=gameType;
  if(gameType==='spin' && ![2,3].includes(playerCount)){
    playerCount=3;
    const playerSelect=$('#playerCountSelect');
    if(playerSelect) playerSelect.value='3';
    try{localStorage.setItem('pokercoach.playerCount','3')}catch(e){}
    if(Object.keys(positionOrder||{}).length) renderTable();
  }
  try{localStorage.setItem('pokercoach.gameType',gameType)}catch(e){}
  invalidateReview();
  scheduleAnalysis();
}

function initGameType(){
  let saved='cash';
  try{saved=localStorage.getItem('pokercoach.gameType')||'cash'}catch(e){}
  if(!GAME_TYPES[saved]) saved='cash';
  const select=$('#gameTypeSelect');
  if(select) select.onchange=()=>selectGameType(select.value);
  selectGameType(saved);
}

function renderTableCapacityControls(){
  const select=$('#tableCapacitySelect');
  if(!select) return;
  if(!select.options.length){
    for(let count=2;count<=10;count++){
      const option=document.createElement('option');
      option.value=String(count);
      option.textContent=String(count);
      select.appendChild(option);
    }
    select.onchange=()=>chooseTableCapacity(Number(select.value));
  }
  select.value=String(tableMaxSeats);
}

async function chooseTableCapacity(count){
  if(!Number.isInteger(count)||count<2||count>10) return;
  try{
    const config=await api('/api/vision/config',{table_max_seats:count});
    tableMaxSeats=Number(config.table_max_seats)||count;
    if(playerCount>tableMaxSeats) choosePlayerCount(tableMaxSeats);
    if(dealerSeat>=tableMaxSeats) dealerSeat=0;
    renderTableCapacityControls();
    renderTable();
    try{localStorage.setItem('pokercoach.tableMaxSeats',String(tableMaxSeats))}catch(e){}
  }catch(e){
    const hint=$('#tableHint');
    if(hint) hint.textContent='Não foi possível atualizar a capacidade da mesa.';
  }
}

async function initVisionConfig(){
  try{
    const config=await api('/api/vision/config');
    tableMaxSeats=Number(config.table_max_seats)||9;
  }catch(e){
    try{
      const saved=Number(localStorage.getItem('pokercoach.tableMaxSeats'));
      if(saved>=2&&saved<=10) tableMaxSeats=saved;
    }catch(_e){}
  }
  renderTableCapacityControls();
}

function choosePlayerCount(count){
  playerCount=count;
  if(dealerSeat>=physicalSeatCount()) dealerSeat=0;
  invalidateReview();
  renderTable();
  try{localStorage.setItem('pokercoach.playerCount',String(count))}catch(e){}
  scheduleAnalysis();
}

async function initTable(){
  try{
    positionOrder=await api('/positions.json');
    const select=$('#playerCountSelect');
    if(select){
      select.innerHTML='';
      Object.keys(positionOrder).forEach(count=>{
        const option=document.createElement('option');
        option.value=count;
        option.textContent=count;
        select.appendChild(option);
      });
      select.onchange=()=>choosePlayerCount(Number(select.value));
    }
    try{
      const saved=Number(localStorage.getItem('pokercoach.playerCount'));
      if(positionOrder[saved]) playerCount=saved;
    }catch(e){}
    if(gameType==='spin' && ![2,3].includes(playerCount)) playerCount=3;
    if(select) select.value=String(playerCount);
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

$$('.pre-action').forEach(b=>b.onclick=()=>{
  markVisionManualOverride();
  const f=$('#reviewForm').elements;
  const same=f.situation.value===b.dataset.value;
  $$('.pre-action').forEach(x=>x.classList.remove('active'));
  $$('.pre-pressure-choice').forEach(x=>x.classList.remove('active'));

  if(same){
    f.situation.value='unopened';
    f.preflop_pressure.value='none';
  }else{
    b.classList.add('active');
    f.situation.value=b.dataset.value;
    f.preflop_pressure.value=b.dataset.value==='limped'?'none':'medium';
    if(b.dataset.value!=='limped'){
      const defaultPressure=$('.pre-pressure-choice[data-value="medium"]');
      if(defaultPressure) defaultPressure.classList.add('active');
    }
  }
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

$$('.pre-pressure-choice').forEach(b=>b.onclick=()=>{
  markVisionManualOverride();
  const f=$('#reviewForm').elements;
  $$('.pre-pressure-choice').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  f.preflop_pressure.value=b.dataset.value;
  const representative=preflopRepresentative(b.dataset.value,f.stack_bb.value);
  if(representative>0) f.open_to_bb.value=String(representative);
  invalidateReview();
  scheduleAnalysis();
});

function resetPostAction(){
  const f=$('#reviewForm').elements;
  f.post_action.value='checked_to_hero';
  f.bet_pressure.value='none';
  f.call_bb.value=0;
  $$('.pressure-choice').forEach(x=>x.classList.remove('active'));
  $$('.post-state').forEach(x=>{
    x.classList.toggle('active',x.dataset.value==='checked_to_hero');
  });
  if($('#betPressure')) $('#betPressure').hidden=true;
}

function resetPreflopAction(){
  const f=$('#reviewForm').elements;
  f.situation.value='unopened';
  f.preflop_pressure.value='none';
  $$('.pre-action,.pre-pressure-choice').forEach(x=>x.classList.remove('active'));
  if($('#preflopPressure')) $('#preflopPressure').hidden=true;
}

$$('.post-state').forEach(b=>b.onclick=()=>{
  markVisionManualOverride();
  const f=$('#reviewForm').elements;
  $$('.post-state').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  f.post_action.value=b.dataset.value;
  if(b.dataset.value==='checked_to_hero'){
    f.bet_pressure.value='none';
    f.call_bb.value=0;
    $$('.pressure-choice').forEach(x=>x.classList.remove('active'));
    $('#betPressure').hidden=true;
  }else{
    $('#betPressure').hidden=false;
  }
  invalidateReview();
  syncContext();
  scheduleAnalysis();
});

$$('.pressure-choice').forEach(b=>b.onclick=()=>{
  markVisionManualOverride();
  const f=$('#reviewForm').elements;
  $$('.pressure-choice').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  f.post_action.value='facing_bet';
  f.bet_pressure.value=b.dataset.value;
  $$('.post-state').forEach(x=>x.classList.toggle('active',x.dataset.value==='facing_bet'));
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
  if(street!==lastStreet){
    visionManualOverrideKey='';
    visionAutoLastSignature='';
    if(f.effective_stack_bb) f.effective_stack_bb.value='';
    if(f.auto_player_action) f.auto_player_action.value='0';
    if(street==='preflop'){
      resetPostAction();
    }else{
      resetPostAction();
    }
    lastStreet=street;
  }
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

  const preNeedsPressure=!postflop && ['facing_raise','facing_3bet'].includes(f.situation.value);
  if($('#preflopPressure')) $('#preflopPressure').hidden=!preNeedsPressure;

  const facingBet=postflop && f.post_action.value==='facing_bet';
  if($('#betPressure')) $('#betPressure').hidden=!facingBet;
  $$('.post-state').forEach(x=>x.classList.toggle('active',x.dataset.value===f.post_action.value));
  if(!facingBet){
    f.bet_pressure.value='none';
    f.call_bb.value=0;
  }
}

$('#reviewForm').addEventListener('input',e=>{
  if(e.target.matches('input,select')){
    if(e.target.name==='stack_bb') updatePressureLabels();
    invalidateReview();
    scheduleAnalysis();
  }
});

$('#reviewForm').addEventListener('change',()=>{
  invalidateReview();
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
  const heroRaw=state?.hero_stack_bb;
  const potRaw=state?.pot_bb;
  const heroBB=heroRaw==null?0:Number(heroRaw);
  const potBB=potRaw==null?0:Number(potRaw);
  const signature=JSON.stringify([heroRaw??null,potRaw??null]);

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
    updatePressureLabels();
    changed=true;
  }
  if(potBB>0){
    if(Math.abs(Number(f.pot_bb.value||0)-potBB)>0.01){
      f.pot_bb.value=potBB.toFixed(2);
      updatePressureLabels();
      changed=true;
    }
  }else if(potRaw===null && Number(f.pot_bb.value||0)>0){
    // A calibrated pot region was read, but no current "Pote: X BB" label
    // was confirmed. Clear the old value instead of analyzing a stale pot.
    f.pot_bb.value='0';
    updatePressureLabels();
    changed=true;
  }

  if(changed){
    invalidateReview('PokerVision: stack/pote atualizados');
    syncContext();
    scheduleAnalysis();
  }
}

function currentVisionStreetKey(){
  const f=$('#reviewForm')?.elements;
  if(!f) return '';
  return [
    f.card1?.value||'',
    f.card2?.value||'',
    f.street?.value||'preflop',
    ...boardFields.map(key=>f[key]?.value||'')
  ].join('|');
}

function markVisionManualOverride(){
  visionManualOverrideKey=currentVisionStreetKey();
  const status=$('#playerAutoStatus');
  if(status) status.textContent='Ações dos jogadores: override manual nesta rua.';
}

function setVisionPlayerAutoEnabled(enabled){
  visionPlayerAutoEnabled=Boolean(enabled);
  const button=$('#playerAutoToggle');
  if(button) button.textContent=visionPlayerAutoEnabled?'Jogadores AUTO ON':'Jogadores AUTO OFF';
  try{localStorage.setItem('pokercoach.playerAutoEnabled',visionPlayerAutoEnabled?'1':'0')}catch(e){}
  const status=$('#playerAutoStatus');
  if(status && !visionPlayerAutoEnabled){
    status.textContent='Ações dos jogadores: automático pausado · controles manuais ativos.';
  }
}

function mappedVisionPlayers(){
  const mapped=mapObservationsToCurrentSeats(
    visionSeatObservations,
    physicalSeatCount()
  );
  const positions=physicalPositionMap();
  const players=[];
  mapped.forEach((obs,seat)=>{
    players.push({...obs,seat,position:positions.get(seat)||''});
  });
  return players;
}

function visionPlayerUsable(player,maxStale=4){
  if(!player) return false;
  if(player.status==='inactive') return false;
  if(player.status==='disconnected') return false;
  if(player.stale && Number(player.last_seen_age||999)>maxStale) return false;
  return true;
}

function normalizedPlayerEvents(players){
  const events=[];
  players.forEach(player=>{
    if(!visionPlayerUsable(player,4)) return;
    const history=Array.isArray(player.action_history)?player.action_history:[];
    if(history.length){
      history.forEach(event=>{
        const action=String(event?.action||'UNKNOWN').toUpperCase();
        if(action==='UNKNOWN') return;
        events.push({
          action,
          bet_bb:event?.bet_bb==null?null:Number(event.bet_bb),
          at:Number(event?.at||0),
          player
        });
      });
    }else{
      const action=String(player.action||'UNKNOWN').toUpperCase();
      if(action!=='UNKNOWN'){
        events.push({
          action,
          bet_bb:player.bet_bb==null?null:Number(player.bet_bb),
          at:Number(player.action_at||0),
          player
        });
      }
    }
  });
  events.sort((a,b)=>{
    const ta=Number(a.at||0), tb=Number(b.at||0);
    if(ta!==tb) return ta-tb;
    return Number(a.bet_bb||0)-Number(b.bet_bb||0);
  });
  return events;
}

function playerEffectiveStack(player,heroStack){
  if(!player) return null;
  const remaining=Number(player.stack_bb);
  const bet=Number(player.bet_bb);
  let total=Number.isFinite(remaining)&&remaining>=0?remaining:null;
  if(total!=null && Number.isFinite(bet)&&bet>0 && String(player.action||'').toUpperCase()!=='ALL-IN'){
    total+=bet;
  }
  if(total==null || total<=0) return null;
  return Math.min(Math.max(0,Number(heroStack)||0),total);
}

function classifyPreflopPressure(amount,action){
  if(String(action).toUpperCase()==='ALL-IN') return 'allin';
  const value=Number(amount);
  if(!Number.isFinite(value)||value<=0) return 'none';
  if(value<=2.5) return 'low';
  if(value<=4) return 'medium';
  return 'high';
}

function classifyPostflopPressure(amount,pot,action){
  if(String(action).toUpperCase()==='ALL-IN') return 'allin';
  const bet=Number(amount), currentPot=Number(pot);
  if(!Number.isFinite(bet)||bet<=0||!Number.isFinite(currentPot)||currentPot<=0) return 'none';
  const before=Math.max(0.1,currentPot>bet?currentPot-bet:currentPot);
  const ratio=bet/before;
  if(ratio<=0.42) return 'low';
  if(ratio<=0.72) return 'medium';
  return 'high';
}

function setAutomaticPreflopUI(situation,pressure){
  const f=$('#reviewForm').elements;
  f.situation.value=situation;
  f.preflop_pressure.value=pressure||'none';
  $$('.pre-action').forEach(button=>{
    button.classList.toggle('active',button.dataset.value===situation);
  });
  $$('.pre-pressure-choice').forEach(button=>{
    button.classList.toggle('active',button.dataset.value===pressure);
  });
  syncContext();
}

function setAutomaticPostflopUI(pressure){
  const f=$('#reviewForm').elements;
  f.post_action.value='facing_bet';
  f.bet_pressure.value=pressure;
  $$('.post-state').forEach(button=>{
    button.classList.toggle('active',button.dataset.value==='facing_bet');
  });
  $$('.pressure-choice').forEach(button=>{
    button.classList.toggle('active',button.dataset.value===pressure);
  });
  if($('#betPressure')) $('#betPressure').hidden=false;
}

function applyVisionPlayerAutomation(state){
  const f=$('#reviewForm')?.elements;
  if(!f) return;

  // V3.14: names/actions/folds from table OCR are diagnostic only. They are
  // not reliable enough to steer a decision. Manual action controls remain
  // the source of truth; table OCR contributes only stack context.
  f.auto_player_action.value='0';
  f.effective_stack_bb.value='';

  const players=mappedVisionPlayers().filter(player=>
    player.seat!==0
    && player.status!=='inactive'
    && Number.isFinite(Number(player.stack_bb))
    && stackReadingIsStable(player)
  );
  const stacks=players.map(player=>Number(player.stack_bb)).filter(value=>value>0);
  state.opponent_stacks_bb=stacks;

  const meter=$('#visionPlayers');
  if(meter){
    meter.textContent=`Mesa: ${playerCount} jogadores · stacks ${stacks.length}/${Math.max(0,playerCount-1)} lidos`;
    meter.classList.toggle('ready',stacks.length>=Math.max(1,playerCount-2));
  }
}

function applyVisionTableState(state){
  if(!visionEnabled || !state?.running) return;

  visionLastState=state;
  visionTableState=String(state?.table_scan_state||'disabled');
  visionInactivePoints=Array.isArray(state?.inactive_points)?state.inactive_points:[];
  visionInactiveSeatIndices=Array.isArray(state?.inactive_seat_indices)
    ? state.inactive_seat_indices.map(Number).filter(Number.isInteger)
    : [];
  visionSeatObservations=Array.isArray(state?.seat_observations)?state.seat_observations:[];
  renderTable();
  const count=Number(state?.detected_player_count||0);
  const inactive=Number(state?.inactive_seats??0);
  const maxSeats=Number(state?.table_max_seats||0);
  if(Number.isInteger(maxSeats)&&maxSeats>=2&&maxSeats<=10&&maxSeats!==tableMaxSeats){
    tableMaxSeats=maxSeats;
    renderTableCapacityControls();
  }
  const scanAt=Number(state?.table_scan_at||0);
  const age=scanAt>0 ? Math.max(0,(Date.now()/1000)-scanAt) : Infinity;
  const fresh=visionTableState==='confirmed' && age<=6;
  const meter=$('#visionPlayers');

  if(fresh && Number.isInteger(count) && count>=2 && count<=10){
    visionPendingPlayerCount=count;
    visionPendingInactiveSeats=Number.isFinite(inactive)?inactive:null;
    visionPendingMaxSeats=Number.isInteger(maxSeats)?maxSeats:null;
    visionPendingConfirmedAt=scanAt;

    const physicalActiveCount=activePhysicalSeats().length;
    if(
      physicalActiveCount===count
      && positionOrder?.[count]
      && playerCount!==count
    ){
      playerCount=count;
      try{
        localStorage.setItem('pokercoach.playerCount',String(count));
      }catch(e){}
      const select=$('#playerCountSelect');
      if(select) select.value=String(count);
      renderTable();
    }
    if(meter){
      const inactiveText=visionPendingInactiveSeats!=null
        ? ` · ${visionPendingInactiveSeats} ausente(s)/vazio(s)`
        : '';
      const maxText=visionPendingMaxSeats
        ? ` de ${visionPendingMaxSeats}`
        : '';
      meter.textContent=`Próxima mão: ${count} jogadores${maxText}${inactiveText} · leitura confirmada`;
      meter.classList.add('ready');
    }
  }else if(meter){
    meter.classList.remove('ready');
    if(visionTableState==='error'){
      meter.textContent=`Jogadores: ERRO na automação · mantendo ${playerCount} · modo básico ativo`;
    }else if(visionTableState==='partial'){
      meter.textContent=`Jogadores: leitura parcial · mantendo ${playerCount} · modo básico ativo`;
    }else if(visionTableState==='disabled'){
      meter.textContent=`Jogadores: automação da mesa desativada · usando ${playerCount}`;
    }else{
      meter.textContent=`Jogadores: leitura desatualizada/aguardando · mantendo ${playerCount}`;
    }
  }

  renderVisionHealthOverlay();
  applyVisionPlayerAutomation(state);
}

function applyPendingPlayerCountForNewHand(){
  const count=Number(visionPendingPlayerCount||0);
  const age=visionPendingConfirmedAt>0
    ? Math.max(0,(Date.now()/1000)-visionPendingConfirmedAt)
    : Infinity;

  // Fail-safe: an old/partial/error read never changes the next hand.
  if(visionTableState!=='confirmed' || age>6) return false;
  if(!Number.isInteger(count) || count<2 || count>10) return false;
  if(!positionOrder?.[count]) return false;
  if(playerCount===count) return false;

  playerCount=count;
  if(dealerSeat>=physicalSeatCount()) dealerSeat=0;
  try{localStorage.setItem('pokercoach.playerCount',String(count))}catch(e){}
  renderTable();
  const meter=$('#visionPlayers');
  if(meter){
    meter.textContent=`Mão atual: ${count} jogadores · contagem congelada no início`;
    meter.classList.add('ready');
  }
  return true;
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
  const previousHand=[f.card1.value,f.card2.value].filter(Boolean).join('|');
  const incomingHand=hand.join('|');
  if(board.length===0 && incomingHand && incomingHand!==previousHand){
    resetPreflopAction();
    resetPostAction();
    visionManualOverrideKey='';
    visionAutoLastSignature='';
    lastStreet='preflop';
    applyPendingPlayerCountForNewHand();
  }
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
    visionLastState=state;

    if(state.connected && state.running && visionEnabled){
      applyVisionNumericState(state);
      applyVisionTableState(state);
    }

    if(!state.connected){
      visionTableState='error';
      renderVisionHealthOverlay();
      setVisionBar('disconnected','PokerVision ainda não enviou dados ao Beelink · modo básico disponível');
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
    visionTableState='error';
    renderVisionHealthOverlay();
    const meter=$('#visionPlayers');
    if(meter) meter.textContent=`Jogadores: sem sincronização · mantendo ${playerCount} · modo básico ativo`;
    const details=$('#visionPlayerDetails');
    if(details) details.textContent='Leitura individual: sem sincronização; modo básico continua disponível.';
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
  if(!f.position.value){
    const state=buildPhysicalPositionState();
    const hero=state.map.get(0);
    if(hero){
      f.position.value=hero;
      $('#heroPosition').textContent=hero;
      applyPositionColor($('#heroPosition'),hero);
      applyPositionColor($('.position-readout'),hero);
    }else{
      return 'Selecione o assento do botão para iniciar a posição.';
    }
  }
  if(!f.card1.value||!f.card2.value)
    return 'Escolha suas duas cartas.';
  const n=boardCount();
  if(n===1||n===2)
    return 'Complete as três cartas do flop.';
  if(f.street.value==='preflop'&&['facing_raise','facing_3bet'].includes(f.situation.value)
      &&(!f.preflop_pressure.value||f.preflop_pressure.value==='none'))
    return 'Escolha BAIXO, MÉDIO, ALTO ou ALL-IN.';
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
  data.quick_preflop=true;
  data.preflop_pressure=f.preflop_pressure?.value||'none';
  data.call_bb=f.post_action?.value==='facing_bet'
    ? Number(f.call_bb?.value||0)
    : 0;
  data.bet_pressure=f.post_action?.value==='facing_bet'?(f.bet_pressure.value||'none'):'none';
  data.effective_stack_bb='';
  data.auto_player_action=false;
  data.opponent_stacks_bb=mappedVisionPlayers()
    .filter(player=>player.seat!==0 && Number.isFinite(Number(player.stack_bb)))
    .map(player=>Number(player.stack_bb));
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
  const invalidState=r.action==='ESTADO INVÁLIDO';
  const mixedState=r.action==='MIXED';
  box.innerHTML=`
    <div class="decision ${escapeHTML(String(r.action).toLowerCase().replaceAll(' ','-'))}">${escapeHTML(label)}</div>
    ${uncovered?'<div class="coverage-warning">O motor ainda não possui range suficiente para transformar este cenário em DESISTIR / PAGAR / AUMENTAR sem inventar uma estratégia.</div>':''}
    ${invalidState?'<div class="coverage-warning">Sequência impossível para a posição atual. Confira onde está o botão antes de usar qualquer range.</div>':''}
    ${mixedState?'<div class="coverage-warning">Estratégia mista: existe range para o spot, mas a ação depende de frequência/linha que a entrada atual não separa completamente.</div>':''}
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
updatePressureLabels();
initGameType();
initTable();
initVisionConfig();
initPokerVision();
