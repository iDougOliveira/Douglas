"""Deterministic, source-attributed NLHE study engine; no live solver or LLM."""
import json
import math
from pathlib import Path

from spin_strategy import decide_spin

ENGINE_VERSION = "3.17.1"
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
    "bet_sizing": {"title": "PokerCoaching — bet sizing: 25–33%, 50–67%, 75–100% do pote", "url": "https://pokercoaching.com/cheatsheets/"},
    "spr": {"title": "GTO Wizard — stack-to-pot ratio (SPR)", "url": "https://blog.gtowizard.com/stack-to-pot-ratio/"},
    "double_paired": {"title": "Upswing — estratégia em boards duplamente pareados", "url": "https://upswingpoker.com/double-paired-boards/"},
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
    if mode not in {"cash", "tournament", "spin"}:
        raise ValueError("Formato inválido.")
    card1, card2 = str(data.get("card1", "")).strip().upper(), str(data.get("card2", "")).strip().upper()
    hand = normalize_hand(card1, card2)
    hero_stack = number(data, "stack_bb", 100, 0.1)
    opponent_stacks = []
    raw_opponents = data.get("opponent_stacks_bb") or []
    if isinstance(raw_opponents, (list, tuple)):
        for raw_stack in raw_opponents[:9]:
            try:
                value = float(raw_stack)
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and value > 0:
                opponent_stacks.append(value)

    raw_effective = data.get("effective_stack_bb")
    if raw_effective in (None, "", 0, "0"):
        effective_stack = hero_stack
        effective_from_vision = False
    else:
        effective_stack = min(
            hero_stack,
            number(data, "effective_stack_bb", hero_stack, 0.1),
        )
        effective_from_vision = bool(data.get("auto_player_action"))

    # Spin strategy is driven by effective BB, not a fixed starting stack.
    # PokerVision already relays stable opponent stacks without using OCR
    # actions as decision inputs. For HU this is exact; for 3-handed the
    # dedicated module labels the shortest-stack approximation explicitly.
    if mode == "spin" and opponent_stacks:
        effective_stack = min([hero_stack] + opponent_stacks)
        effective_from_vision = True

    return {"players": n, "position": pos, "mode": mode,
            "stack": hero_stack,
            "effective_stack": effective_stack,
            "effective_from_vision": effective_from_vision,
            "opponent_stacks": opponent_stacks,
            "hand": hand, "hole": [card1, card2],
            "ante": number(data, "ante_bb", 0)}

def preflop_order(n):
    return POSITIONS[n] if n == 2 else POSITIONS[n][3:] + POSITIONS[n][:3]

def result_base(c):
    return {"engine_version": ENGINE_VERSION, "hand": c["hand"], "position": c["position"], "player_count": c["players"],
            "hero_stack_bb": c["stack"], "effective_stack_bb": c["effective_stack"],
            "action": "SEM COBERTURA", "sizing": "Cenário sem cobertura estratégica", "range": "Não disponível",
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
    if c["mode"] == "spin":
        return decide_spin(data, c, r, postflop)
    if street != "preflop":
        return postflop(data, c, r)
    situation = data.get("situation", "unopened")
    if situation not in {"unopened", "facing_raise", "limped", "facing_3bet", "facing_4bet"}:
        raise ValueError("Ação anterior inválida.")
    if c["mode"] == "tournament" and data.get("icm_pressure") is not False:
        r["notes"].append("Confirme nos ajustes se há bolha, mesa final, satélite ou pressão de premiação. Estes perfis não calculam ICM nem bounty.")
        return r
    if data.get("quick_preflop") and situation != "unopened":
        return quick_preflop_response(data, c, r)
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

def preflop_pressure_representative(stack, pressure):
    """Representative observed raise size for the simplified preflop UI.

    Low/medium anchors reflect common published open sizes (2–2.5 BB online,
    3–4 BB live/SB). 'High' is treated as an out-of-standard large open and
    represented by 5 BB because the implemented 3-bet guideline only covers
    opens through 5 BB.
    """
    stack = max(0.0, float(stack or 0))
    values = {"low": 2.25, "medium": 3.5, "high": 5.0, "allin": stack}
    return min(stack, values.get(pressure, 0.0))


def postflop_pressure_ranges(pot, stack):
    """Standard postflop bet-size buckets, expressed in BB.

    Source buckets:
      low    = 25–33% pot
      medium = 50–67% pot
      high   = 75–100% pot
      allin  = hero remaining stack

    Non-all-in buckets are capped below the hero stack; an impossible bucket
    returns None.
    """
    pot = max(0.0, float(pot or 0))
    stack = max(0.0, float(stack or 0))
    if pot <= 0 or stack <= 0:
        return {"low": None, "medium": None, "high": None, "allin": (stack, stack)}

    step = 0.1
    def bucket(lo_frac, hi_frac):
        low = round(pot * lo_frac, 2)
        high = round(min(pot * hi_frac, stack - step), 2)
        if low > high or low >= stack:
            return None
        return (low, high)

    return {
        "low": bucket(.25, .33),
        "medium": bucket(.50, .67),
        "high": bucket(.75, 1.00),
        "allin": (stack, stack),
    }


def postflop_pressure_representative(pot, stack, pressure):
    ranges = postflop_pressure_ranges(pot, stack)
    selected = ranges.get(pressure)
    if not selected:
        return 0.0
    low, high = selected
    if pressure == "allin":
        return high
    return round((low + high) / 2.0, 4)



def _quick_open_profile(c):
    """Reuse the documented RFI profile as a conservative limp/isolation gate."""
    if c["mode"] == "cash":
        profile_id = "cash6_100" if c["players"] <= 6 else "cash8_reference"
    else:
        ids = ["mtt8_10", "mtt9_75", "mtt9_100"]
        profile_id = min(
            ids,
            key=lambda k: (
                abs(PROFILES[k]["stack"] - c["stack"]),
                abs(PROFILES[k]["players"] - c["players"]),
            ),
        )
    profile = PROFILES[profile_id]
    pos = c["position"]
    aliases = {"BTN/SB": "SB", "UTG+2": "UTG+1", "MP": "UTG+2"}
    if pos not in profile["ranges"]:
        pos = aliases.get(pos, pos)
    if pos not in profile["ranges"] and pos == "UTG+2":
        pos = "UTG+1"
    return profile, pos


def _quick_vs_open_ranges(c):
    """Deterministic unknown-opener baseline built from public guidance.

    Because quick mode deliberately omits villain position, this is not labeled
    as an exact solver chart. It keeps the universally published value core,
    adds the published late-position extensions/bluffs, and uses a BB calling
    bucket made from the hand classes public sources explicitly identify as
    good calls (medium pairs, suited connectors and broadways).
    """
    late = c["position"] in {"CO", "BTN", "SB", "BB", "BTN/SB"}
    value = expand_range("QQ+ AKs AKo")
    if late:
        value |= expand_range("JJ+ AQs+ AKo")

    bluff = set()
    if c["position"] in {"BTN", "SB", "BTN/SB"}:
        bluff = {"A2s", "A3s", "A4s", "A5s"}

    # The BB is the main flat-calling exception in deep, no-ante cash theory.
    bb_calls = set()
    if c["position"] == "BB":
        bb_calls |= expand_range(
            "22+ A2s+ K9s+ Q9s+ J9s+ T8s+ 98s 87s 76s 65s ATo+ KJo+ QJo"
        )
        bb_calls -= value

    return value, bluff, bb_calls


def quick_preflop_response(data, c, r):
    """Reduced-input but decisive preflop baseline for replay/study mode."""
    situation = str(data.get("situation", "unopened"))
    pressure = str(data.get("preflop_pressure", "none")).lower()
    decision_stack = min(c["stack"], c.get("effective_stack", c["stack"]))
    if c.get("effective_from_vision"):
        r["notes"].append(
            f"Stack efetivo automático contra o agressor detectado: "
            f"{decision_stack:g} BB (hero {c['stack']:g} BB)."
        )
    r["quick_preflop"] = True
    r["bet_pressure"] = pressure
    source(r, "charts", "threebet", "defense", "rules")

    if situation == "limped":
        profile, range_pos = _quick_open_profile(c)
        if range_pos not in profile["ranges"]:
            # Even an unsupported alias must still end decisively.
            r.update(
                action="FOLD" if c["position"] != "BB" else "CHECK",
                sizing="Desistir" if c["position"] != "BB" else "Passar no big blind",
                strategy_status="study_heuristic",
                profile="Limp · baseline conservador",
            )
            return r

        playable = expand_range(profile["ranges"][range_pos])
        r.update(
            profile=f"Limp · isolamento pelo range de abertura {profile['name']}",
            strategy_status="study_heuristic",
            range=profile["ranges"][range_pos],
            range_hands=sorted(playable),
        )
        if c["hand"] in playable:
            size = min(c["stack"], 4.0)
            r.update(
                action="RAISE",
                sizing=f"Isolar para ~{size:g} BB",
                raise_to_bb=size,
            )
            r["notes"].append(
                "Modo rápido contra limp: usa o range de abertura documentado da posição "
                "como limiar conservador para isolar. É uma simplificação, não um chart exato de iso-raise."
            )
        else:
            action = "CHECK" if c["position"] == "BB" else "FOLD"
            r.update(
                action=action,
                sizing="Passar no big blind" if action == "CHECK" else "Desistir",
            )
            r["notes"].append(
                "A mão está fora do range de abertura usado como limiar de isolamento."
            )
        return r

    if situation == "facing_raise":
        if pressure not in {"low", "medium", "high", "allin"}:
            pressure = "medium"
        auto_open = data.get("open_to_bb") if data.get("auto_player_action") else None
        try:
            auto_open_value = float(auto_open) if auto_open not in (None, "") else 0.0
        except (TypeError, ValueError):
            auto_open_value = 0.0
        opening = (
            min(decision_stack, auto_open_value)
            if auto_open_value > 0
            else preflop_pressure_representative(decision_stack, pressure)
        )
        r["open_to_bb"] = opening

        value, bluff, bb_calls = _quick_vs_open_ranges(c)
        r.update(
            profile="Vs raise · baseline teórico com opener desconhecido",
            strategy_status="study_heuristic",
            range_hands=sorted(value | bluff | bb_calls),
            range="3-bet valor QQ+/AK; JJ/AQs em posições finais; A2s-A5s como blefes tardios; BB pode pagar classes jogáveis",
        )
        r["notes"].append(
            "A posição de quem abriu não é informada no modo rápido. Portanto a resposta é um baseline "
            "conservador, não um chart solver específico de posição contra posição."
        )

        if pressure == "allin":
            if c["hand"] in expand_range("QQ+ AKs AKo"):
                r.update(action="CALL", sizing=f"Pagar all-in até {decision_stack:g} BB", call_bb=decision_stack)
            else:
                r.update(action="FOLD", sizing="Desistir contra o all-in")
            return r

        if c["hand"] in value or c["hand"] in bluff:
            multiple = 4.0 if c["position"] in {"SB", "BB", "BTN/SB"} else 3.5
            size = min(decision_stack, round(max(opening * multiple, 2 * opening - 1), 2))
            r.update(
                action="RAISE" if size < decision_stack else "ALL-IN",
                sizing=(
                    f"Aumentar para ~{size:g} BB"
                    if size < decision_stack
                    else f"ALL-IN {decision_stack:g} BB"
                ),
                raise_to_bb=size,
            )
            return r

        if c["hand"] in bb_calls:
            invested = 1.0
            call = max(0.0, round(opening - invested, 2))
            if call < decision_stack:
                r.update(action="CALL", sizing=f"Pagar ~{call:g} BB", call_bb=call)
            else:
                r.update(action="FOLD", sizing="Desistir; o valor exigiria comprometer todo o stack")
            return r

        r.update(action="FOLD", sizing="Desistir")
        return r

    if situation in {"facing_3bet", "facing_4bet"}:
        if pressure not in {"low", "medium", "high", "allin"}:
            pressure = "medium"

        premium = expand_range("QQ+ AKs AKo")
        late = c["position"] in {"CO", "BTN", "SB", "BB", "BTN/SB"}
        calls = expand_range("JJ AQs KQs")
        if late:
            calls |= expand_range("99+ AQs KQs")

        r.update(
            profile="Vs re-raise · baseline conservador 100 BB",
            strategy_status="study_heuristic",
            range_hands=sorted(premium | calls),
            range="QQ+/AK continuam agressivamente; JJ/AQs/KQs e, em posição tardia, 99+ formam a faixa conservadora de continuação",
        )
        r["notes"].append(
            "Sem posição do 3-bettor, o modo rápido usa uma continuação conservadora. "
            "Ranges exatos de call/4-bet mudam por posição, rake e tamanho."
        )

        if pressure == "allin":
            if c["hand"] in premium:
                r.update(action="CALL", sizing=f"Pagar all-in até {decision_stack:g} BB", call_bb=decision_stack)
            else:
                r.update(action="FOLD", sizing="Desistir contra o all-in")
            return r

        if c["hand"] in premium:
            representative = preflop_pressure_representative(decision_stack, pressure)
            size = min(decision_stack, max(10.0, round(representative * 2.5, 2)))
            r.update(
                action="RAISE" if size < decision_stack else "ALL-IN",
                sizing=(
                    f"4-bet para ~{size:g} BB"
                    if size < decision_stack
                    else f"ALL-IN {decision_stack:g} BB"
                ),
                raise_to_bb=size,
            )
        elif c["hand"] in calls and pressure in {"low", "medium"}:
            r.update(action="CALL", sizing="Pagar o re-raise")
        else:
            r.update(action="FOLD", sizing="Desistir")
        return r

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

    board_rc = Counter(c[0] for c in board)
    board_pair_ranks = sorted(
        (RANKS.index(rank) + 2 for rank, count in board_rc.items() if count >= 2),
        reverse=True,
    )
    board_double_paired = len(board_pair_ranks) >= 2

    private_improvement = False
    shared_kicker_value = max(RANKS.index(h[0]) + 2 for h in hole)
    shared_kicker_rank = RANKS[shared_kicker_value - 2]

    # On a double-paired board (e.g. 6-6-5-5), "two pair" may belong to the
    # board rather than to Hero. A pocket pair only replaces the lower board
    # pair if it ranks above that lower pair. Matching 6x/5x is already caught
    # by a stronger full-house category above.
    if board_double_paired and category == "two_pair":
        if pocket:
            pocket_value = RANKS.index(hole[0][0]) + 2
            private_improvement = pocket_value > board_pair_ranks[1]

    board_only_two_pair = (
        board_double_paired
        and category == "two_pair"
        and not private_improvement
    )

    board_trip_rank = next(
        (rank for rank, count in board_rc.items() if count >= 3),
        None,
    )
    board_trips_full_house = bool(
        board_trip_rank and category == "full_house"
    )
    full_house_pair_value = None
    top_board_side_value = None
    if board_trip_rank:
        side_values = [
            RANKS.index(rank) + 2
            for rank in board_rc
            if rank != board_trip_rank
        ]
        if side_values:
            top_board_side_value = max(side_values)
        pair_values = [
            RANKS.index(rank) + 2
            for rank, count in rc.items()
            if rank != board_trip_rank and count >= 2
        ]
        if pair_values:
            full_house_pair_value = max(pair_values)

    board_owned_full_house = False
    if board_trip_rank and category == "full_house":
        board_side_pairs = [
            rank for rank, count in board_rc.items()
            if rank != board_trip_rank and count >= 2
        ]
        board_owned_full_house = bool(board_side_pairs)

    return {
        "category": category,
        "label": label,
        "score": score,
        "top_pair": top_pair,
        "overpair": overpair,
        "flush_draw": flush_draw,
        "straight_draw": straight_draw,
        "outs": outs,
        "board_double_paired": board_double_paired,
        "board_only_two_pair": board_only_two_pair,
        "private_improvement": private_improvement,
        "shared_kicker_rank": shared_kicker_rank,
        "shared_kicker_value": shared_kicker_value,
        "board_trip_rank": board_trip_rank,
        "board_trips_full_house": board_trips_full_house,
        "full_house_pair_value": full_house_pair_value,
        "top_board_side_value": top_board_side_value,
        "board_owned_full_house": board_owned_full_house,
    }

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
    source(r,"odds","texture","cbet","bet_sizing","spr","double_paired")
    r.update(board=board, board_text=" ".join(board), hand_class=info["label"],
             board_texture=texture["label"], strategy_status="study_heuristic",
             profile="Pós-flop automático · força da mão + textura + pressão/pot odds")
    r["notes"].append(f"Board: {' '.join(board)}. Mão atual: {info['label']}. Textura do flop: {texture['label']}.")
    r["notes"].append("A ação pós-flop é uma heurística determinística baseada em força feita, draws, textura e pot odds; não substitui um solver de ranges.")

    pot = number(data,"pot_bb",0,0)
    call = number(data,"call_bb",0,0)
    pressure = str(data.get("bet_pressure", "none")).lower()
    if pot <= 0:
        raise ValueError("Informe o pote atual para analisar o pós-flop.")

    decision_stack = min(c["stack"], c.get("effective_stack", c["stack"]))
    r["hero_stack_pot_ratio"] = round(c["stack"] / pot, 3)
    if c.get("effective_from_vision"):
        r["spr"] = round(decision_stack / pot, 3)
        r["notes"].append(
            f"Stack efetivo automático: {decision_stack:g} BB; "
            f"SPR aproximado {decision_stack:g}/{pot:g} = {r['spr']:.2f}."
        )
    else:
        r["notes"].append(
            f"Relação stack/pote do hero: {c['stack']:g}/{pot:g} = "
            f"{r['hero_stack_pot_ratio']:.2f}. Sem um adversário identificado "
            "com stack confiável, o motor mantém o contexto baseado no stack do hero."
        )

    if call > c["stack"]:
        if data.get("auto_player_action"):
            r["notes"].append(
                f"Leitura automática pediu {call:g} BB, acima do stack do hero; "
                f"o valor foi limitado a {c['stack']:g} BB."
            )
            call = c["stack"]
        else:
            raise ValueError("O valor para pagar não pode exceder seu stack.")

    if call <= 0 and pressure in {"low", "medium", "high", "allin"}:
        ranges = postflop_pressure_ranges(pot, decision_stack)
        selected = ranges.get(pressure)
        if not selected:
            raise ValueError("Essa faixa de aposta excede seu stack; use ALL-IN.")
        call = postflop_pressure_representative(pot, decision_stack, pressure)
        r["call_bb"] = call
        r["bet_pressure"] = pressure
        low, high = selected
        pct_low = {"low": 25, "medium": 50, "high": 75, "allin": None}[pressure]
        pct_high = {"low": 33, "medium": 67, "high": 100, "allin": None}[pressure]
        if pressure == "allin":
            r["notes"].append(
                f"Pressão selecionada: ALL-IN. Continuar exige até {call:g} BB, "
                "o stack restante informado pelo PokerVision."
            )
        else:
            r["notes"].append(
                f"Pressão selecionada: {pressure.upper()}. Pela referência de sizing, "
                f"essa faixa é {pct_low}–{pct_high}% do pote; com pote de {pot:g} BB, "
                f"equivale a {low:g}–{high:g} BB. O motor usa {call:g} BB como ponto médio."
            )
        if data.get("auto_player_action"):
            r["notes"].append(
                "Quando o PokerVision fornece o valor exato para pagar, esse valor "
                "tem prioridade sobre a aproximação por faixa."
            )
        else:
            r["notes"].append(
                "O ponto médio é uma aproximação operacional para revisão rápida; "
                "não substitui o tamanho exato da aposta."
            )
    if call > 0 and data.get("auto_player_action"):
        r["call_bb"] = round(call, 4)
        r["bet_pressure"] = pressure
        r["notes"].append(
            f"Ação automática dos jogadores: valor atual para pagar = {call:g} BB."
        )

    opponents = int(number(data,"active_opponents",1,1,9))
    if opponents > 1:
        r["notes"].append("Pote multiway: o modo de estudo usa uma linha mais conservadora.")

    # A full house on a tripled board can be much weaker than the label
    # suggests. Example: Hero 66 on A-4-4-K-4 has 44466, while any Ax,
    # Kx, or higher pocket pair can make a superior full house. Never route
    # these hands through the generic "full house = automatic stack-off" path.
    if info["board_trips_full_house"]:
        pair_value = info["full_house_pair_value"] or 0
        top_side = info["top_board_side_value"] or 0
        top_full_house = pair_value >= top_side and top_side > 0
        pair_rank = RANKS[pair_value - 2] if pair_value >= 2 else "?"
        r["hand_class"] = f"full house em board triplicado · par {pair_rank}"
        r["notes"].append(
            "O board já contém uma trinca. O full house precisa ser avaliado "
            "pela força do par complementar; não é tratado como stack-off automático."
        )

        if info["board_owned_full_house"]:
            r["notes"].append(
                "O próprio board já forma full house para todos; as cartas privadas "
                "servem principalmente para desempate."
            )
            if call > 0:
                r.update(action="FOLD", sizing="Evitar compromisso grande sem vantagem privada clara")
            else:
                r.update(action="CHECK", sizing="Passar; full house é compartilhado pelo board")
            return r

        if not top_full_house:
            r["notes"].append(
                "Seu par complementar não é o maior rank lateral do board. "
                "Existem vários full houses superiores possíveis."
            )
            if call > 0:
                if pressure in {"high", "allin"}:
                    r.update(
                        action="FOLD",
                        sizing="Desistir; full house relativo fraco para pressão grande",
                    )
                else:
                    r.update(
                        action="CALL",
                        sizing=f"Pagar {min(call, c['stack']):g} BB sem aumentar",
                    )
            else:
                r.update(
                    action="CHECK",
                    sizing="Passar; valor relativo insuficiente para empilhar automaticamente",
                )
            return r

        r["notes"].append(
            "Seu par complementar usa o maior rank lateral do board; "
            "é uma versão forte deste padrão, mas ainda não ignora stack/pot."
        )

    # Critical distinction: two pair can be entirely on the board. In that
    # case Hero does NOT own a normal two-pair value hand; the hole cards are
    # mostly acting as a kicker. Do not route this through the generic
    # score>=2 value-raise logic.
    if info["board_double_paired"] and info["category"] == "two_pair":
        if info["board_only_two_pair"]:
            r["hand_class"] = f"dois pares da mesa + kicker {info['shared_kicker_rank']}"
            r["notes"].append(
                f"Os dois pares estão no board e são compartilhados por todos. "
                f"Sua contribuição é o kicker {info['shared_kicker_rank']}; "
                "isso não deve ser tratado como dois pares próprios para aumentar por valor."
            )
        else:
            r["notes"].append(
                "O board está duplamente pareado. Sua mão melhora o board com um pocket pair, "
                "mas ainda não é tratada como valor automático para raise."
            )

        if call > 0:
            # Conservative bluff-catcher baseline when villain range is unknown.
            # Never value-raise a plain two-pair classification on a double-paired
            # board. Kicker thresholds tighten as the observed bet gets larger.
            if info["private_improvement"]:
                r.update(action="CALL", sizing=f"Pagar {call:g} BB")
            else:
                kicker = info["shared_kicker_value"]
                min_kicker = {
                    "low": 11,      # J+
                    "medium": 13,   # K+
                    "high": 14,     # A only
                    "allin": 15,    # no board-only kicker auto-calls a shove
                    "none": 13,
                }.get(pressure, 13)
                if kicker >= min_kicker and pressure != "allin":
                    r.update(action="CALL", sizing=f"Pagar {call:g} BB como bluff-catcher")
                else:
                    r.update(action="FOLD", sizing="Desistir; board compartilhado e kicker insuficiente")
            return r

        # Checked to Hero: the engine must not value-bet merely because the
        # board itself shows two pair. Range-specific bluffs/value bets need a
        # stronger model than the current heuristic, so default to check.
        r.update(action="CHECK", sizing="Passar; dois pares estão na mesa")
        return r

    if call > 0:
        pot_odds = 100*call/(pot+call)
        r["pot_odds_pct"] = pot_odds
        if info["score"] >= 2:
            action = "RAISE" if info["score"] >= 3 or texture["wet"] else "CALL"
            if pressure == "allin":
                action = "ALL-IN"
                sizing = f"Continuar exige o stack: ~{call:g} BB"
            else:
                sizing = "Aumentar por valor" if action=="RAISE" else f"Pagar {call:g} BB"
            r.update(action=action, sizing=sizing)
        elif info["overpair"] or info["top_pair"]:
            action = "ALL-IN" if pressure == "allin" else "CALL"
            r.update(
                action=action,
                sizing=f"Continuar exige o stack: ~{call:g} BB" if action=="ALL-IN" else f"Pagar {call:g} BB"
            )
        elif info["outs"]:
            draw_equity = min(60, info["outs"] * (4 if len(board)==3 else 2))
            r["estimated_draw_equity_pct"] = draw_equity
            continue_draw = draw_equity >= pot_odds
            action = ("ALL-IN" if pressure == "allin" else "CALL") if continue_draw else "FOLD"
            r.update(
                action=action,
                sizing=(
                    f"Continuar exige o stack: ~{call:g} BB"
                    if action=="ALL-IN"
                    else f"Pagar {call:g} BB"
                    if action=="CALL"
                    else "Pot odds insuficientes para o draw"
                )
            )
            r["notes"].append(f"Estimativa didática pela regra 4/2: ~{draw_equity:.1f}% para {info['outs']} outs versus {pot_odds:.1f}% de pot odds.")
        else:
            r.update(action="FOLD", sizing="Sem força/draw suficiente para pagar")
        return r

    # Ninguém apostou antes da decisão do herói.
    def set_bet(frac, label):
        target = round(pot * frac, 2)
        actual = round(min(target, c["stack"]), 2)
        if actual >= c["stack"]:
            r.update(
                action="ALL-IN",
                sizing=f"All-in {actual:g} BB; sizing alvo de {target:g} BB excede o stack",
                bet_bb=actual,
            )
        else:
            r.update(
                action="BET",
                sizing=label,
                bet_bb=actual,
            )

    if info["score"] >= 2:
        frac = .67 if texture["wet"] else .50
        set_bet(frac, f"Apostar ~{frac:.0%} do pote")
    elif info["overpair"] or info["top_pair"]:
        frac = .50 if texture["wet"] else .33
        set_bet(frac, f"Apostar ~{frac:.0%} do pote")
    elif info["outs"] >= 8:
        frac = .50 if texture["wet"] else .33
        set_bet(frac, f"Semi-blefe ~{frac:.0%} do pote")
    elif data.get("situation","unopened") == "unopened" and not texture["wet"] and opponents == 1:
        set_bet(.33, "C-bet pequena ~33% do pote")
    else:
        r.update(action="CHECK", sizing="Passar a ação")
    return r
