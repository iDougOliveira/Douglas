"""Deterministic, source-attributed NLHE study engine; no live solver or LLM."""
import json
import math
from pathlib import Path

ENGINE_VERSION = "3.1.0"
POSITIONS = {int(k): v for k, v in json.loads((Path(__file__).parent / "static/positions.json").read_text()).items()}
RANKS = "23456789TJQKA"
SOURCES = {
    "charts": {"title": "PokerCoaching — resumos públicos de ranges pré-flop", "url": "https://pokercoaching.com/preflop-charts/"},
    "threebet": {"title": "Upswing — 3-bet, posição e sizing a 100 BB", "url": "https://upswingpoker.com/3-bet-strategy-aggressive-preflop/"},
    "odds": {"title": "Upswing — cálculo de pot odds", "url": "https://upswingpoker.com/pot-odds-step-by-step/"},
    "rules": {"title": "Poker TDA — regras de raises", "url": "https://www.pokertda.com/view-poker-tda-rules/"},
    "stacks": {"title": "GTO Wizard — influência do stack", "url": "https://blog.gtowizard.com/how-stack-sizes-change-your-range/"},
    "texture": {"title": "Upswing — fundamentos de textura de flop", "url": "https://upswingpoker.com/board-texture-tips/"},
    "cbet": {"title": "PokerCoaching — fundamentos pós-flop e c-bet", "url": "https://pokercoaching.com/blog/gto-postflop-basics/"},
    "defense": {"title": "PokerCoaching — 3-bet e defesa pré-flop", "url": "https://pokercoaching.com/preflop-charts/"},
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
    card1, card2 = str(data.get("card1", "")).strip().upper(), str(data.get("card2", "")).strip().upper()
    hand = normalize_hand(card1, card2)
    return {"players": n, "position": pos, "mode": mode,
            "stack": number(data, "stack_bb", 100, 0.1),
            "hand": hand, "hole": [card1, card2],
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
    if c["mode"] == "cash":
        profile_id = "cash6_100" if c["players"] <= 6 else "cash8_reference"
    else:
        ids = ["mtt8_10", "mtt9_75", "mtt9_100"]
        profile_id = min(ids, key=lambda k: (abs(PROFILES[k]["stack"]-c["stack"]), abs(PROFILES[k]["players"]-c["players"])))
    profile = PROFILES[profile_id]
    range_pos = c["position"]
    aliases = {"BTN/SB": "SB", "UTG+2": "UTG+1", "MP": "UTG+2"}
    if range_pos not in profile["ranges"]:
        range_pos = aliases.get(range_pos, range_pos)
    if range_pos not in profile["ranges"] and range_pos == "UTG+2":
        range_pos = "UTG+1"
    if range_pos not in profile["ranges"]:
        r["notes"].append("A posição atual não possui referência compatível no estudo carregado.")
        return r
    adapted = profile["players"] != c["players"] or profile["stack"] != c["stack"] or range_pos != c["position"]
    r.update(profile=profile["name"], profile_id=profile_id,
             strategy_status="adapted_reference" if adapted else "published_summary",
             range=profile["ranges"][range_pos], study_position=range_pos,
             study_stack_bb=profile["stack"], study_players=profile["players"])
    if adapted:
        r["notes"].append(f"Correspondência automática: mesa {c['players']}-max / {c['stack']:g} BB foi comparada ao estudo {profile['players']}-max / {profile['stack']:g} BB usando a posição {range_pos}.")
        source(r, "stacks")
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
    elif profile_id == "mtt8_10":
        r.update(action="ALL-IN", sizing=f"Até {c['stack']:g} BB no total", raise_to_bb=c["stack"], additional_bb=c["stack"])
        r["notes"].append("Para manter uma ação única no modo de estudo de 10 BB, o app usa o ramo all-in para as mãos incluídas no conjunto publicado.")
    else:
        size = profile["open_bb"] or 2.5
        r.update(action="RAISE", sizing=f"Até {size:g} BB no total", raise_to_bb=size, additional_bb=size)
        if profile["open_bb"] is None:
            r["notes"].append("O resumo não informa sizing para este perfil; o app usa 2,5 BB como convenção explícita de estudo.")
        if c["position"] == "SB":
            r["notes"].append("A fonte mistura limp e raise no SB; para uma resposta única, o modo simplificado escolhe o ramo RAISE.")
        r["notes"].append(f"{c['hand']} está no conjunto de abertura publicado para {range_pos}.")
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

def _card(card):
    card = str(card or "").strip().upper()
    if len(card) != 2 or card[0] not in RANKS or card[1] not in "CDHS":
        raise ValueError("Carta do board inválida.")
    return card

def _board(data, street, hole):
    keys = ["flop1", "flop2", "flop3", "turn", "river"]
    expected = {"flop": 3, "turn": 4, "river": 5, "postflop": 3}.get(street, 0)
    cards = [_card(data.get(k)) for k in keys if data.get(k)]
    if street == "postflop":
        if len(cards) not in {3,4,5}:
            raise ValueError("Complete o flop para analisar o pós-flop.")
    elif len(cards) != expected:
        raise ValueError(f"Para {street}, informe {expected} cartas comunitárias.")
    all_cards = list(hole) + cards
    if len(set(all_cards)) != len(all_cards):
        raise ValueError("Uma mesma carta não pode aparecer duas vezes.")
    return cards

def _straight_high(ranks):
    vals = sorted(set(RANKS.index(r)+2 for r in ranks), reverse=True)
    if 14 in vals:
        vals.append(1)
    for high in range(14,4,-1):
        if all(v in vals for v in range(high-4, high+1)):
            return high
    return None

def _hand_info(hole, board):
    from collections import Counter
    cards = hole + board
    rc = Counter(c[0] for c in cards)
    sc = Counter(c[1] for c in cards)
    flush_suit = next((s for s,n in sc.items() if n >= 5), None)
    straight = _straight_high([c[0] for c in cards])
    groups = sorted(rc.values(), reverse=True)
    if 4 in groups:
        category, label, score = "quads", "quadra", 7
    elif 3 in groups and groups.count(2) + max(groups.count(3)-1,0) >= 1:
        category, label, score = "full_house", "full house", 6
    elif flush_suit:
        category, label, score = "flush", "flush", 5
    elif straight:
        category, label, score = "straight", "sequência", 4
    elif 3 in groups:
        category, label, score = "trips", "trinca", 3
    elif groups.count(2) >= 2:
        category, label, score = "two_pair", "dois pares", 2
    elif 2 in groups:
        category, label, score = "pair", "um par", 1
    else:
        category, label, score = "high_card", "carta alta", 0

    board_vals = [RANKS.index(c[0]) for c in board]
    top_rank = board[max(range(len(board)), key=lambda i: board_vals[i])][0] if board else None
    pocket = hole[0][0] == hole[1][0]
    overpair = bool(board and pocket and RANKS.index(hole[0][0]) > max(board_vals))
    top_pair = any(h[0] == top_rank for h in hole) and rc[top_rank] >= 2 if top_rank else False

    max_suit = max(sc.values()) if sc else 0
    flush_draw = len(board) < 5 and max_suit == 4 and any(sc[h[1]] == 4 for h in hole)

    uniq = set(RANKS.index(c[0])+2 for c in cards)
    if 14 in uniq:
        uniq.add(1)
    straight_out_values = set()
    for low in range(1,11):
        seq=set(range(low,low+5))
        miss=seq-uniq
        if len(miss)==1:
            straight_out_values |= miss
    straight_draw = len(board) < 5 and bool(straight_out_values) and score < 4
    outs = (9 if flush_draw else 0) + (8 if straight_draw else 0)
    if flush_draw and straight_draw:
        outs = min(15, outs)

    return {"category": category, "label": label, "score": score, "top_pair": top_pair,
            "overpair": overpair, "flush_draw": flush_draw, "straight_draw": straight_draw, "outs": outs}

def _texture(board):
    from collections import Counter
    ranks=[RANKS.index(c[0])+2 for c in board[:3]]
    suits=Counter(c[1] for c in board[:3])
    rc=Counter(c[0] for c in board[:3])
    paired=any(v>1 for v in rc.values())
    monotone=max(suits.values(), default=0)==3
    two_tone=max(suits.values(), default=0)==2
    span=max(ranks)-min(ranks) if ranks else 0
    connected=span <= 4 and len(set(ranks)) == 3
    wet = monotone or two_tone or connected
    parts=[]
    if paired: parts.append("pareado")
    if monotone: parts.append("monotone")
    elif two_tone: parts.append("duas cores")
    else: parts.append("rainbow")
    parts.append("conectado" if connected else "desconectado")
    return {"wet": wet, "label": " · ".join(parts)}

def postflop(data,c,r):
    street = data.get("street", "flop")
    board = _board(data, street, c["hole"])
    info = _hand_info(c["hole"], board)
    texture = _texture(board)
    source(r,"odds","texture","cbet")
    r.update(board=board, board_text=" ".join(board), hand_class=info["label"],
             board_texture=texture["label"], strategy_status="study_heuristic",
             profile="Pós-flop automático · força da mão + textura + pot odds")
    r["notes"].append(f"Board: {' '.join(board)}. Mão atual: {info['label']}. Textura do flop: {texture['label']}.")
    r["notes"].append("A ação pós-flop é uma heurística determinística baseada em força feita, draws, textura e pot odds; não substitui um solver de ranges.")

    pot = number(data,"pot_bb",0,0)
    call = number(data,"call_bb",0,0)
    if pot <= 0:
        raise ValueError("Informe o pote atual para analisar o pós-flop.")
    opponents = int(number(data,"active_opponents",1,1,9))
    if opponents > 1:
        r["notes"].append("Pote multiway: o modo de estudo usa uma linha mais conservadora.")

    if call > 0:
        pot_odds = 100*call/(pot+call)
        r["pot_odds_pct"] = pot_odds
        if info["score"] >= 2:
            action = "RAISE" if info["score"] >= 3 or texture["wet"] else "CALL"
            r.update(action=action, sizing="Aumentar por valor" if action=="RAISE" else f"Pagar {call:g} BB")
        elif info["overpair"] or info["top_pair"]:
            r.update(action="CALL", sizing=f"Pagar {call:g} BB")
        elif info["outs"]:
            draw_equity = min(60, info["outs"] * (4 if len(board)==3 else 2))
            r["estimated_draw_equity_pct"] = draw_equity
            r.update(action="CALL" if draw_equity >= pot_odds else "FOLD",
                     sizing=f"Pagar {call:g} BB" if draw_equity >= pot_odds else "Pot odds insuficientes para o draw")
            r["notes"].append(f"Estimativa didática pela regra 4/2: ~{draw_equity:.1f}% para {info['outs']} outs versus {pot_odds:.1f}% de pot odds.")
        else:
            r.update(action="FOLD", sizing="Sem força/draw suficiente para pagar")
        return r

    # Ninguém apostou antes da decisão do herói.
    if info["score"] >= 2:
        frac = .67 if texture["wet"] else .50
        r.update(action="BET", sizing=f"Apostar ~{frac:.0%} do pote", bet_bb=round(pot*frac,2))
    elif info["overpair"] or info["top_pair"]:
        frac = .50 if texture["wet"] else .33
        r.update(action="BET", sizing=f"Apostar ~{frac:.0%} do pote", bet_bb=round(pot*frac,2))
    elif info["outs"] >= 8:
        frac = .50 if texture["wet"] else .33
        r.update(action="BET", sizing=f"Semi-blefe ~{frac:.0%} do pote", bet_bb=round(pot*frac,2))
    elif data.get("situation","unopened") == "unopened" and not texture["wet"] and opponents == 1:
        r.update(action="BET", sizing="C-bet pequena ~33% do pote", bet_bb=round(pot*.33,2))
    else:
        r.update(action="CHECK", sizing="Passar a ação")
    return r
