"""Deterministic, source-attributed NLHE study engine; no live solver or LLM."""
import json
import math
from pathlib import Path

ENGINE_VERSION = "3.0.0"
POSITIONS = {int(k): v for k, v in json.loads((Path(__file__).parent / "static/positions.json").read_text()).items()}
RANKS = "23456789TJQKA"
SOURCES = {
    "charts": {"title": "PokerCoaching — resumos públicos de ranges pré-flop", "url": "https://pokercoaching.com/preflop-charts/"},
    "threebet": {"title": "Upswing — 3-bet, posição e sizing a 100 BB", "url": "https://upswingpoker.com/3-bet-strategy-aggressive-preflop/"},
    "odds": {"title": "Upswing — cálculo de pot odds", "url": "https://upswingpoker.com/pot-odds-step-by-step/"},
    "rules": {"title": "Poker TDA — regras de raises", "url": "https://www.pokertda.com/view-poker-tda-rules/"},
    "stacks": {"title": "GTO Wizard — influência do stack", "url": "https://blog.gtowizard.com/how-stack-sizes-change-your-range/"},
}

# Factual hand-set data from the public text, not copied chart artwork or solver frequencies.
# '+' fixes the first rank and increases the second; pairs increase both ranks.
# Do not substitute the percentages printed on the source page: its text summaries
# and mixed-frequency chart images do not always describe identical combinations.
PROFILES = {
    "cash6_100": {"name": "Cash 6-max · 100 BB · resumo publicado", "mode": "cash", "players": 6, "stack": 100, "open_bb": 2.5, "ranges": {
        "LJ": "66+ A3s+ K8s+ Q9s+ J9s+ T9s ATo+ KJo+ QJo",
        "HJ": "55+ A2s+ K6s+ Q9s+ J9s+ T9s 98s 87s 76s ATo+ KTo+ QTo+",
        "CO": "33+ A2s+ K3s+ Q6s+ J8s+ T7s+ 97s+ 87s 76s A8o+ KTo+ QTo+ JTo",
        "BTN": "33+ A2s+ K2s+ Q3s+ J4s+ T6s+ 96s+ 85s+ 75s+ 64s+ 53s+ A4o+ K8o+ Q9o+ J9o+ T8o+ 98o",
        "SB": "22+ A2s+ K2s+ Q2s+ J2s+ T3s+ 94s+ 84s+ 74s+ 63s+ 53s+ 43s A2o+ K4o+ Q5o+ J7o+ T7o+ 96o+ 86o+ 76o"}},
    "cash8_reference": {"name": "Cash 8-max · resumo publicado · aplicação limitada a 100 BB", "mode": "cash", "players": 8, "stack": 100, "open_bb": 3,
        "caveat": "O texto full-ring não declara stack nem rake. O limite de 100 BB foi escolhido para restringir o uso no app, não foi validado por solver. O tamanho de 3 BB vem da imagem full-ring da fonte.", "ranges": {
        "UTG": "77+ A3s+ K9s+ QTs+ JTs T9s AQo+ KQo",
        "UTG+1": "77+ A3s+ K8s+ QTs+ JTs T9s AJo+ KQo",
        "LJ": "66+ A2s+ K7s+ QTs+ JTs T9s ATo+ KJo+",
        "HJ": "55+ A2s+ K5s+ Q9s+ J9s+ T9s ATo+ KTo+ QJo",
        "CO": "44+ A2s+ K5s+ Q8s+ J8s+ T8s+ 97s+ 87s 76s 65s 54s A8o+ KTo+ QTo+ JTo",
        "BTN": "22+ A2s+ K2s+ Q3s+ J5s+ T6s+ 96s+ 86s+ 76s 65s 54s A3o+ K8o+ Q9o+ J9o+ T9o",
        "SB": "22+ A2s+ K2s+ Q2s+ J2s+ T2s+ 92s+ 84s+ 73s+ 63s+ 52s+ 42s+ A2o+ K2o+ Q3o+ J5o+ T6o+ 96o+ 86o+ 75o+ 65o 54o"}},
    "mtt9_100": {"name": "Torneio 9-max · 100 BB · referência explorativa da fonte", "mode": "tournament", "players": 9, "stack": 100, "open_bb": 2.5, "ranges": {
        "UTG": "66+ A9s+ A5s KTs+ QTs+ JTs T9s 98s AQo+",
        "UTG+1": "66+ A4s+ K9s+ Q9s+ J9s+ T9s 98s AJo+ KQo",
        "UTG+2": "66+ A2s+ K9s+ Q9s+ J9s+ T9s 98s 87s 76s AJo+ KQo",
        "LJ": "44+ A2s+ K9s+ Q9s+ J9s+ T9s 98s 87s 76s 65s ATo+ KJo+",
        "HJ": "22+ A2s+ K8s+ Q9s+ J9s+ T9s 98s 87s 76s 65s 54s ATo+ KJo+",
        "CO": "22+ A2s+ K7s+ Q8s+ J8s+ T8s+ 97s+ 86s+ 75s+ 64s+ 54s 43s A9o+ KJo+",
        "BTN": "22+ A2s+ K2s+ Q2s+ J6s+ T6s+ 96s+ 85s+ 75s+ 64s+ 53s+ 43s 32s A2o+ K7o+ Q8o+ J8o+ T8o+ 97o+ 87o 76o",
        "SB": "22+ A2s+ K2s+ Q2s+ J2s+ T4s+ 94s+ 84s+ 74s+ 63s+ 53s+ 43s 32s A2o+ K2o+ Q2o+ J6o+ T6o+ 96o+ 86o+ 76o"}},
    "mtt9_75": {"name": "Torneio 9-max · 75 BB · resumo publicado", "mode": "tournament", "players": 9, "stack": 75, "open_bb": None, "ranges": {
        "UTG": "66+ A3s+ K9s+ Q9s+ AJo+ KQo",
        "UTG+1": "66+ A3s+ K8s+ Q9s+ J9s+ T9s 98s ATo+",
        "UTG+2": "44+ A2s+ K8s+ Q9s+ J9s+ T8s+ 98s 76s ATo+ KTo+",
        "LJ": "33+ A2s+ K6s+ Q9s+ J8s+ T8s+ 98s 87s 76s A9o+ KTo+ QTo+",
        "HJ": "22+ A2s+ K4s+ Q8s+ J8s+ T7s+ 97s+ 87s 76s 65s 54s A8o+ KTo+ QTo+ JTo",
        "CO": "22+ A2s+ K2s+ Q5s+ J7s+ T6s+ 96s+ 86s+ 75s+ 65s 54s A5o+ K9o+ Q9o+ J9o+ T9o",
        "BTN": "22+ A2s+ K2s+ Q2s+ J3s+ T3s+ 95s+ 85s+ 74s+ 64s+ 53s+ 43s A2o+ K5o+ Q8o+ J8o+ T7o+ 97o+ 87o",
        "SB": "22+ A2s+ K2s+ Q2s+ J2s+ T2s+ 92s+ 82s+ 72s+ 62s+ 52s+ 42s+ 32s A2o+ K2o+ Q2o+ J2o+ T3o+ 95o+ 85o+ 75o+ 64o+ 54o"}},
    "mtt8_10": {"name": "Torneio 8-max · 10 BB · resumo de stack curto", "mode": "tournament", "players": 8, "stack": 10, "open_bb": None, "ranges": {
        "UTG": "44+ A4s+ K9s+ QTs+ J9s+ T9s A9o+ KJo+",
        "UTG+1": "33+ A2s+ K9s+ Q9s+ J9s+ T9s A9o+ KJo+ QJo",
        "LJ": "22+ A2s+ K9s+ Q9s+ J9s+ T9s 98s A7o+ KTo+ QJo",
        "HJ": "22+ A2s+ K9s+ Q9s+ J9s+ T8s+ 98s A3o+ KTo+ QJo JTo",
        "CO": "22+ A2s+ K6s+ Q8s+ J8s+ T8s+ 98s A2o+ KTo+ QTo+ JTo",
        "BTN": "22+ A2s+ K2s+ Q5s+ J6s+ T6s+ 97s+ 87s A2o+ K7o+ QTo+ JTo",
        "SB": "22+ A2s+ K2s+ Q2s+ J2s+ T2s+ 92s+ 82s+ 72s+ 62s+ 52s+ 42s+ 32s A2o+ K2o+ Q2o+ J2o+ T4o+ 95o+ 86o+ 75o+ 65o"}},
}

def expand_range(value):
    hands = set()
    for token in value.split():
        plus = token.endswith("+")
        token = token.rstrip("+")
        a, b = token[:2]
        if a == b:
            hands.update(r+r for r in (RANKS[RANKS.index(a):] if plus else a))
        else:
            suffix = token[2:]
            if suffix not in {"s", "o"} or RANKS.index(a) <= RANKS.index(b):
                raise ValueError("Range inválido")
            hands.update(a+r+suffix for r in (RANKS[RANKS.index(b):RANKS.index(a)] if plus else b))
    return hands

def normalize_hand(card1, card2):
    cards = [str(card1).strip().upper(), str(card2).strip().upper()]
    if any(len(c) != 2 or c[0] not in RANKS or c[1] not in "CDHS" for c in cards):
        raise ValueError("Escolha duas cartas válidas.")
    if cards[0] == cards[1]:
        raise ValueError("As duas cartas não podem ser iguais.")
    cards.sort(key=lambda c: RANKS.index(c[0]), reverse=True)
    a, b = cards
    return a[0]+b[0]+("" if a[0] == b[0] else "s" if a[1] == b[1] else "o")

def number(data, key, default=0, minimum=0, maximum=1e9):
    raw = data.get(key, default)
    try:
        value = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Valor inválido: {key}.")
    if isinstance(raw, bool) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Valor fora dos limites: {key}.")
    return value

def context(data):
    if data.get("completed_hand") is not True:
        raise ValueError("Confirme que é uma simulação ou mão já encerrada.")
    n = number(data, "player_count", 8, 2, 10)
    if int(n) != n:
        raise ValueError("A quantidade de jogadores deve ser inteira.")
    n = int(n)
    pos = str(data.get("position", "BTN")).upper()
    if pos == "MP" and n == 8:
        pos = "LJ"
    if pos not in POSITIONS[n]:
        raise ValueError("Posição incompatível com a mesa.")
    mode = data.get("mode", "cash")
    if mode not in {"cash", "tournament"}:
        raise ValueError("Formato inválido.")
    return {"players": n, "position": pos, "mode": mode,
            "stack": number(data, "stack_bb", 100, 0.1),
            "hand": normalize_hand(data.get("card1", ""), data.get("card2", "")),
            "ante": number(data, "ante_bb", 0)}

def preflop_order(n):
    return POSITIONS[n] if n == 2 else POSITIONS[n][3:] + POSITIONS[n][:3]

def result_base(c):
    return {"engine_version": ENGINE_VERSION, "hand": c["hand"], "position": c["position"], "player_count": c["players"],
            "action": "REVISAR", "sizing": "Cenário sem cobertura", "range": "Não disponível",
            "range_hands": [], "notes": [], "sources": [], "strategy_status": "not_covered", "profile": "Sem perfil compatível",
            "raise_to_bb": None, "additional_bb": None, "disclaimer": "Referência educacional para revisão. Não é um solver GTO nem uma garantia de lucro."}

def source(r, *keys):
    for key in keys:
        if SOURCES[key] not in r["sources"]:
            r["sources"].append(SOURCES[key])

def decide(data):
    c = context(data)
    r = result_base(c)
    street = data.get("street", "preflop")
    if street not in {"preflop", "flop", "turn", "river", "postflop"}:
        raise ValueError("Etapa da mão inválida.")
    if street != "preflop":
        return postflop(data, c, r)
    situation = data.get("situation", "unopened")
    if situation not in {"unopened", "facing_raise", "limped", "facing_3bet", "facing_4bet"}:
        raise ValueError("Ação anterior inválida.")
    if c["mode"] == "tournament" and data.get("icm_pressure") is not False:
        r["notes"].append("Confirme nos ajustes se há bolha, mesa final, satélite ou pressão de premiação. Estes perfis não calculam ICM nem bounty.")
        return r
    if situation == "facing_raise":
        return threebet(data, c, r)
    if situation != "unopened":
        r["notes"].append("Limp, squeeze, 3-bet e 4-bet exigem tabelas específicas. O motor não usa um range de abertura para responder a essas ações.")
        return r
    if c["position"] == "BB":
        r.update(action="SEM AÇÃO", sizing="Você ganhou os blinds", strategy_status="game_rule", profile="Todos desistiram")
        r["notes"].append("Se alguém pagou o blind, selecione 'Houve limp'. Ninguém entrou significa que todos desistiram antes de você.")
        return r
    if c["mode"] == "cash" and c["ante"]:
        r["notes"].append("As referências cash implementadas não são ajustadas para ante ou straddle.")
        return r
    profile_id, profile = next(((k,p) for k,p in PROFILES.items() if (p["mode"],p["players"],p["stack"]) == (c["mode"],c["players"],c["stack"])), (None,None))
    if not profile:
        r["notes"].append("Sem tabela para esta combinação. Perfis: cash 6/8 jogadores a 100 BB; torneio 9 jogadores a 75/100 BB; torneio 8 jogadores a 10 BB. Não há interpolação entre stacks ou mesas.")
        source(r,"stacks")
        return r
    r.update(profile=profile["name"], profile_id=profile_id, strategy_status="published_summary", range=profile["ranges"][c["position"]])
    r["range_hands"] = sorted(expand_range(r["range"]))
    source(r, "charts")
    r["notes"].append("Consulta determinística ao resumo escrito da fonte. As imagens têm ações mistas; não foram importadas frequências nem porcentagens GTO.")
    if profile.get("caveat"):
        r["notes"].append(profile["caveat"])
        r["strategy_status"] = "adapted_reference"
    if c["mode"] == "tournament":
        r["notes"].append("A estrutura exata de ante não está detalhada no resumo público. Referência sem ajuste por premiação, bounty ou comportamento dos adversários.")
    else:
        r["notes"].append("Rake não parametrizado: a referência não é um cálculo específico para a sua sala.")
    if c["hand"] not in r["range_hands"]:
        r.update(action="FOLD", sizing="Fora do resumo de abertura")
        r["notes"].append("FOLD é a classificação deste resumo simplificado; não prova que um solver descarte a mão em todas as frequências.")
    elif c["position"] == "SB" or (profile_id == "mtt8_10" and c["position"] not in {"HJ","CO"}):
        r.update(action="MISTA", sizing="A fonte não separa as ações por mão")
        r["notes"].append("A mão pertence ao conjunto publicado, mas a fonte agrupa raise/limp ou raise/all-in. Não há percentual disponível para escolher uma ação única.")
    elif profile_id == "mtt8_10":
        r.update(action="ALL-IN", sizing=f"Até {c['stack']:g} BB no total", raise_to_bb=c["stack"], additional_bb=c["stack"])
    else:
        size = profile["open_bb"]
        r.update(action="RAISE", sizing=f"Até {size:g} BB no total" if size else "Tamanho não informado no resumo", raise_to_bb=size, additional_bb=size)
        r["notes"].append(f"{c['hand']} está no conjunto de abertura publicado para {c['position']}.")
    return r

def threebet(data, c, r):
    villain = str(data.get("opener_position", "")).upper()
    order = preflop_order(c["players"])
    if villain not in order or order.index(villain) >= order.index(c["position"]):
        r["notes"].append("Selecione a posição de quem fez o primeiro aumento, antes de você na ordem pré-flop.")
        return r
    opening = number(data, "open_to_bb", data.get("last_raise_bb", 0))
    if opening < 2:
        raise ValueError("Informe o total do primeiro raise (mínimo 2 BB para um raise completo). Exemplo: aumentou PARA 5 BB → informe 5.")
    invested = .5 if c["position"] in {"SB","BTN/SB"} else 1 if c["position"] == "BB" else 0
    call = round(opening-invested, 4)
    if data.get("call_bb") not in (None, "") and not math.isclose(number(data,"call_bb"),call,abs_tol=0.01):
        raise ValueError(f"Valores incompatíveis: o total de {opening:g} BB exige pagar {call:g} BB nesta posição.")
    r.update(call_bb=call, min_raise_to_bb=round(2*opening-1, 4))
    source(r,"threebet","rules")
    if c["mode"] != "cash" or c["stack"] != 100 or c["ante"]:
        r["notes"].append("A diretriz de 3-bet implementada se aplica apenas a cash, 100 BB e sem ante. O mínimo legal informado não é uma recomendação estratégica.")
        return r
    if number(data,"callers",0,0,9) != 0 or opening > 5:
        r["notes"].append("A implementação limita esta diretriz a um único open entre 2 e 5 BB, sem callers. Squeeze e opens maiores não estão modelados.")
        return r
    r.update(profile="3-bet por valor · diretriz Upswing · cash 100 BB", strategy_status="expert_guideline", range="QQ+ AKs AKo", range_hands=sorted(expand_range("QQ+ AKs AKo")))
    if c["hand"] not in r["range_hands"]:
        r["notes"].append("A diretriz cobre o núcleo de valor QQ+/AK. Fora dele, não é correto deduzir FOLD: faltam ranges completos de call e blefes contra esta posição.")
        r["strategy_status"] = "not_covered"
        return r
    # Postflop order starts at SB (at BB for heads-up), ends at BTN.
    post_order = ["BB", "BTN/SB"] if c["players"] == 2 else POSITIONS[c["players"]][1:] + ["BTN"]
    ip = post_order.index(c["position"]) > post_order.index(villain)
    multiple = 3 if ip else 4
    size = round(max(opening*multiple,r["min_raise_to_bb"]), 4)
    r.update(action="RAISE", sizing=f"3-bet até {size:g} BB no total", raise_to_bb=size, additional_bb=round(size-invested, 4), in_position=ip)
    r["notes"].extend([f"Diretriz de valor, não solução exata: {c['hand']} pertence ao núcleo QQ+/AK descrito pela fonte.", f"Contra {villain}, você está {'em posição' if ip else 'fora de posição'} no pós-flop: {multiple} × {opening:g} = {size:g} BB no total.", f"Você já colocou {invested:g} BB; acrescentaria {size-invested:g} BB. Mínimo legal: {r['min_raise_to_bb']:g} BB.", "A fonte sugere cerca de 3× em posição e 4–4,5× fora. Usamos 4× como simplificação explícita; não há otimização por rake ou adversário."])
    return r

def postflop(data,c,r):
    pot = number(data,"pot_bb",0,0.01)
    call = number(data,"call_bb",0)
    source(r,"odds")
    r.update(profile="Pot odds e EV de call no encerramento da ação", strategy_status="math_only", pot_odds_pct=100*call/(pot+call))
    r["notes"].append(f"Pote antes do seu call, já incluindo a aposta adversária: {pot:g} BB. Call: {call:g} BB. Equity de equilíbrio: {r['pot_odds_pct']:.2f}% (sem rake).")
    remaining = number(data,"remaining_bb",c["stack"])
    if call > pot or call > remaining:
        raise ValueError("Confira pote e call. Side pots e calls acima do stack disponível não são suportados.")
    if c["mode"] != "cash" or call == 0 or data.get("closes_action") is not True or number(data,"active_opponents",1,1,9) != 1:
        r["notes"].append("A decisão por EV exige cash, um adversário, aposta a pagar e confirmação de que o call encerra todas as apostas (river ou all-in sem side pot). Equity isolada não define bet/check.")
        return r
    if data.get("estimated_equity") in (None, ""):
        r["notes"].append("Informe a equity contra o range adversário. Este cálculo não estima equity a partir das suas duas cartas.")
        return r
    equity = number(data,"estimated_equity",0,0,100)/100
    ev = equity*(pot+call)-call
    r.update(action="INDIFERENTE" if math.isclose(ev,0,abs_tol=1e-9) else "CALL" if ev>0 else "FOLD", sizing=f"Pagar {call:g} BB" if ev>0 else "EV igual a zero" if math.isclose(ev,0,abs_tol=1e-9) else "EV do call negativo", ev_call_bb=ev)
    r["notes"].append(f"EV do call = equity × (pote + call) − call = {ev:.3f} BB. Resultado condicionado à equity informada, à ausência de rake adicional e ao encerramento da ação.")
    return r
