const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST':'GET', headers:{'Content-Type':'application/json'}, body:body?JSON.stringify(body):undefined});
  const j = await r.json(); if(!r.ok) throw new Error(j.error||'Falha na operação'); return j;
}
async function login(){try{await api('/api/login',{password:$('#password').value});$('#login').hidden=true;$('#app').hidden=false;loadSummary()}catch(e){$('#loginMsg').textContent=e.message}}
$$('.tab').forEach(b=>b.onclick=()=>{$$('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.tab).classList.add('active');if(b.dataset.tab==='bankroll')loadSummary()});
function formData(form){const d=Object.fromEntries(new FormData(form));form.querySelectorAll('input[type=number]').forEach(i=>d[i.name]=i.value);d.completed_hand=form.elements.completed_hand?.checked===true;return d}
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
    b.onclick=()=>{dealerSeat=i;$('#result').hidden=true;renderTable()};seats.appendChild(b);
  });
  const heroOffset=(playerCount-dealerSeat)%playerCount,heroPos=positionOrder[playerCount][heroOffset];
  $('#heroPosition').textContent=heroPos;$('#reviewForm').elements.position.value=heroPos;
  $('#reviewForm').elements.player_count.value=playerCount;
  $('#tableHint').textContent=playerCount===2?'Heads-up: o botão também é o small blind e age primeiro no pré-flop.':'Escolha quantos jogadores receberam cartas no início da mão, incluindo você. LJ é o assento antes do HJ.';
  $$('.player-count').forEach(b=>{const selected=Number(b.dataset.count)===playerCount;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected))});
}
function choosePlayerCount(count){playerCount=count;dealerSeat=Math.min(dealerSeat,count-1);$('#result').hidden=true;renderTable();try{localStorage.setItem('pokercoach.playerCount',String(count))}catch(e){}}
async function initTable(){try{positionOrder=await api('/positions.json');const controls=$('#playerCounts');controls.innerHTML='';Object.keys(positionOrder).forEach(count=>{const b=document.createElement('button');b.type='button';b.className='player-count';b.dataset.count=count;b.textContent=count;b.setAttribute('aria-label',`${count} jogadores`);b.onclick=()=>choosePlayerCount(Number(count));controls.appendChild(b)});try{const saved=Number(localStorage.getItem('pokercoach.playerCount'));if(positionOrder[saved])playerCount=saved}catch(e){}renderTable();$('.analyze-btn').disabled=false}catch(e){$('#tableHint').textContent='Não foi possível carregar a mesa. Atualize a página.'}}
$$('.choice').forEach(b=>b.onclick=()=>{$$(`.choice[data-field="${b.dataset.field}"]`).forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#reviewForm').elements[b.dataset.field].value=b.dataset.value});
$$('.action-choice').forEach(b=>b.onclick=()=>{$$('.action-choice').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#reviewForm').elements.situation.value=b.dataset.value});
$('#advancedToggle').onclick=()=>{const a=$('#advanced');a.hidden=!a.hidden;$('#advancedToggle span').textContent=a.hidden?'⌄':'⌃'};
const suitData=[['s','♠','black'],['h','♥','red'],['d','♦','red'],['c','♣','black']],ranks=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];
function buildDeck(){const deck=$('#deck');deck.innerHTML='';ranks.forEach(rank=>suitData.forEach(([code,symbol,color])=>{const card=rank+code.toUpperCase(),btn=document.createElement('button');btn.type='button';btn.className=`pick-card ${color}`;btn.dataset.card=card;btn.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;btn.onclick=()=>selectCard(card,rank,symbol,color);deck.appendChild(btn)}))}
function openPicker(slot){activeCardSlot=slot;$('#pickerLabel').textContent=slot==='card1'?'Primeira carta':'Segunda carta';$$('.pick-card').forEach(b=>{const other=slot==='card1'?$('#reviewForm').elements.card2.value:$('#reviewForm').elements.card1.value;b.disabled=b.dataset.card===other});$('#cardPicker').hidden=false}
function selectCard(card,rank,symbol,color){$('#reviewForm').elements[activeCardSlot].value=card;const slot=$(`.card-slot[data-slot="${activeCardSlot}"]`);slot.className=`card-slot selected ${color}`;slot.innerHTML=`<b>${rank}</b><span>${symbol}</span>`;$('#cardPicker').hidden=true}
$$('.card-slot').forEach(b=>b.onclick=()=>openPicker(b.dataset.slot));$('#closePicker').onclick=()=>$('#cardPicker').hidden=true;$('#cardPicker').onclick=e=>{if(e.target.id==='cardPicker')e.currentTarget.hidden=true};
$('#reviewForm').onsubmit=async e=>{e.preventDefault();const box=$('#result');if(!e.target.card1.value||!e.target.card2.value){box.hidden=false;box.innerHTML='<p class="error">Escolha as duas cartas.</p>';return}if(!$('#studyConfirm').checked){box.hidden=false;box.innerHTML='<p class="error">Confirme que é uma simulação ou mão encerrada.</p>';return}const data=formData(e.target);data.completed_hand=true;try{const r=await api('/api/analyze',data);box.hidden=false;box.scrollIntoView({behavior:'smooth',block:'center'});box.innerHTML=`<div class="decision ${r.action.toLowerCase()}">${r.action}</div><h2>${r.hand} · ${r.sizing}</h2><p><b>Posição:</b> ${data.position} &nbsp; <b>Range-base:</b> ${r.range}</p><ul>${r.notes.map(n=>`<li>${n}</li>`).join('')}</ul><small>${r.disclaimer}</small>`}catch(err){box.hidden=false;box.innerHTML=`<p class="error">${err.message}</p>`}};
$('#sessionForm').onsubmit=async e=>{e.preventDefault();try{await api('/api/session',formData(e.target));e.target.reset();e.target.played_at.value=new Date().toISOString().slice(0,10);loadSummary()}catch(err){alert(err.message)}};
async function loadSummary(){try{const s=await api('/api/summary');$('#summary').innerHTML=`<div class="kpis"><div><b>${s.sessions}</b><span>Sessões</span></div><div><b>${Number(s.profit).toFixed(2)}</b><span>Resultado</span></div><div><b>${Number(s.invested).toFixed(2)}</b><span>Total entradas</span></div></div><h3>Últimas sessões</h3>${s.recent.length?`<div class="table"><table><tr><th>Data</th><th>Modo</th><th>Limite</th><th>Entrada</th><th>Saída</th></tr>${s.recent.map(x=>`<tr><td>${x[0]}</td><td>${x[1]}</td><td>${x[2]}</td><td>${x[3]}</td><td>${x[4]}</td></tr>`).join('')}</table></div>`:'<p>Nenhuma sessão registrada.</p>'}`}catch(e){}}
$('#sessionForm').played_at.value=new Date().toISOString().slice(0,10);
buildDeck();initTable();
