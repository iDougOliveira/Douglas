"""Spin & Go study engine for PokerCoach.

The module intentionally uses public textual strategy summaries instead of copying
solver chart images/frequencies. It is deterministic and only runs through the
existing completed-hand/simulation guard in strategy.py.
"""

RANKS = "23456789TJQKA"

SPIN_SOURCES = {
    "rules": {
        "title": "PokerStars — estrutura atual do Spin & Go",
        "url": "https://www.pokerstars.com/pt-BR/poker/spin-and-go/",
    },
    "course": {
        "title": "PokerStars Learn — curso de Spin & Go",
        "url": "https://www.pokerstars.com/poker/learn/course/spin-go-strategy-pokerstars-tips/",
    },
    "btn3": {
        "title": "PokerStars Learn — 3-handed pré-flop no Button",
        "url": "https://www.pokerstars.com/poker/learn/strategies/spin-go-preflop-on-the-button/",
    },
    "sb3": {
        "title": "PokerStars Learn — 3-handed no Small Blind",
        "url": "https://www.pokerstars.com/poker/learn/strategies/spin-go-preflop-in-the-small-blind/",
    },
    "bb3": {
        "title": "PokerStars Learn — 3-handed no Big Blind",
        "url": "https://www.pokerstars.com/poker/learn/strategies/spin-go-preflop-in-the-big-blind/",
    },
    "hubtn": {
        "title": "PokerStars Learn — Heads-Up no Button",
        "url": "https://www.pokerstars.com/poker/learn/strategies/spin-go-heads-up-preflop-on-the-button/",
    },
    "hubb": {
        "title": "PokerStars Learn — Heads-Up no Big Blind",
        "url": "https://www.pokerstars.com/poker/learn/strategies/spin-go-heads-up-preflop-in-the-big-blind/",
    },
    "gto": {
        "title": "GTO Wizard — Spins com stacks simétricos e assimétricos",
        "url": "https://blog.gtowizard.com/new-spins-solutions-study-plans-and-ev-comparison/",
    },
    "preflop_solver": {
        "title": "PreflopRanges — Spin & Go solved charts 8–25 BB",
        "url": "https://preflopranges.app/charts/spins/25bb",
    },
}


def _source(result, *keys):
    for key in keys:
        item = SPIN_SOURCES[key]
        if item not in result["sources"]:
            result["sources"].append(item)


def _expand_range(value):
    hands = set()
    for token in value.split():
        plus = token.endswith("+")
        token = token.rstrip("+")
        if len(token) < 2:
            raise ValueError("Range Spin inválido")
        a, b = token[:2]
        if a not in RANKS or b not in RANKS:
            raise ValueError("Range Spin inválido")
        if a == b:
            ranks = RANKS[RANKS.index(a):] if plus else a
            hands.update(r + r for r in ranks)
            continue
        suffix = token[2:]
        if suffix not in {"s", "o"} or RANKS.index(a) <= RANKS.index(b):
            raise ValueError("Range Spin inválido")
        ranks = RANKS[RANKS.index(b):RANKS.index(a)] if plus else b
        hands.update(a + r + suffix for r in ranks)
    return hands


def _pairs(low, high):
    lo = RANKS.index(low)
    hi = RANKS.index(high)
    if lo > hi:
        lo, hi = hi, lo
    return {r + r for r in RANKS[lo:hi + 1]}


def _specific(*values):
    out = set()
    for value in values:
        if isinstance(value, str):
            out |= _expand_range(value)
        else:
            out |= set(value)
    return out


def _set_range(result, profile, notation, hands, stack, status="published_text_summary"):
    result.update(
        profile=profile,
        strategy_status=status,
        range=notation,
        range_hands=sorted(hands),
        study_stack_bb=stack,
    )


def _effective(c):
    return max(0.1, min(c["stack"], c.get("effective_stack", c["stack"])))


def _all_suited(hand):
    return len(hand) == 3 and hand.endswith("s")


def _rank_index(rank):
    return RANKS.index(rank)


def _offsuit_at_least(hand, high, low_floor):
    if len(hand) != 3 or not hand.endswith("o"):
        return False
    return hand[0] == high and _rank_index(hand[1]) >= _rank_index(low_floor)


def _spin_header(result, c):
    depth = _effective(c)
    result["spin_mode"] = True
    result["spin_phase"] = "heads_up" if c["players"] == 2 else "three_handed"
    result["effective_stack_bb"] = depth
    result["notes"].append(
        f"Spin & Go: {'heads-up' if c['players'] == 2 else '3-handed'} · "
        f"stack efetivo usado pelo motor: {depth:g} BB."
    )
    if c.get("opponent_stacks"):
        result["notes"].append(
            "Stacks adversários detectados: "
            + ", ".join(f"{x:g} BB" for x in c["opponent_stacks"])
            + ". Em 3-handed, a V3.17.1 usa o menor stack como aproximação conservadora; "
              "spots assimétricos completos continuam marcados como simplificação."
        )
        _source(result, "gto")
    _source(result, "rules", "course")
    return depth


def _fold(result, reason="Desistir"):
    result.update(action="FOLD", sizing=reason)
    return result


def _call(result, amount=None, reason="Pagar"):
    result.update(action="CALL", sizing=reason)
    if amount is not None:
        result["call_bb"] = round(float(amount), 4)
    return result


def _raise(result, total, reason=None):
    total = round(float(total), 4)
    result.update(
        action="RAISE",
        sizing=reason or f"Aumentar para {total:g} BB no total",
        raise_to_bb=total,
    )
    return result


def _shove(result, depth):
    depth = round(float(depth), 4)
    result.update(
        action="ALL-IN",
        sizing=f"ALL-IN até {depth:g} BB efetivos",
        raise_to_bb=depth,
    )
    return result


def _limp(result, reason="Completar / limp"):
    result.update(action="LIMP", sizing=reason)
    return result


def _mixed(result, reason, profile=None):
    result.update(
        action="MIXED",
        sizing=reason,
        strategy_status="mixed_published_strategy",
    )
    if profile:
        result["profile"] = profile
    return result


def _invalid_state(result, reason):
    result.update(
        action="ESTADO INVÁLIDO",
        sizing=reason,
        strategy_status="invalid_state",
        profile="Spin & Go · sequência impossível",
    )
    result["notes"].append(
        "Corrija a posição do botão ou a ação anterior; o motor não transforma um estado impossível em range."
    )
    return result


def _nearest_standard_depth(depth):
    return min((8, 10, 15, 20, 25), key=lambda value: abs(value - depth))


def _three_btn(data, c, result, depth):
    _source(result, "btn3", "preflop_solver")
    situation = data.get("situation", "unopened")

    # In 3-handed Spin the BTN is first to act preflop. A limp or ordinary
    # raise cannot already exist before the BTN's first decision. If Hero
    # opened and now faces a re-raise, the UI must use facing_3bet.
    if situation in {"limped", "facing_raise"}:
        return _invalid_state(
            result,
            "BTN 3-handed não pode enfrentar LIMP/RAISE antes de sua primeira ação. Verifique o botão.",
        )

    if situation in {"facing_3bet", "facing_4bet"}:
        _set_range(
            result,
            "Spin 3h BTN · resposta a re-raise",
            "A resposta depende de quem re-aumentou, sizing e stack pareado",
            _all_hands(),
            _nearest_standard_depth(depth),
            "mixed_published_strategy",
        )
        result["notes"].append(
            "Este é um ramo válido depois de Hero abrir, mas a interface rápida ainda não informa qual blind "
            "re-aumentou. O motor marca MISTA em vez de inventar uma frequência única."
        )
        return _mixed(
            result,
            "MISTA — informe o agressor/sizing exato para separar call, shove e fold",
        )

    if situation != "unopened":
        return _invalid_state(result, "Sequência pré-flop não reconhecida para BTN 3-handed.")

    bucket = _nearest_standard_depth(depth)
    # Majority-play sets published in text by the solved-chart source. At 8 BB
    # the BTN solution is push/fold. At 10 BB the source mixes shove/min-raise;
    # PokerStars' textual course is used only to keep the premium min-raise core.
    majority_ranges = {
        8: "22+ A2s+ K4s+ Q8s+ J8s+ T7s+ 97s+ 86s+ 76s+ 65s+ A2o+ K9o+ QTo+ JTo+",
        10: "22+ A2s+ K4s+ Q7s+ J7s+ T8s+ 97s+ 87s+ 76s+ A2o+ K9o+ QTo+ JTo+",
        15: "22+ A2s+ K5s+ Q7s+ J8s+ T7s+ 97s+ 86s+ 76s+ A5o+ K9o+ QTo+ JTo+ T9o+",
        20: "44+ A2s+ K4s+ Q5s+ J7s+ T7s+ 96s+ 86s+ 75s+ 65s+ 54s+ A7o+ A5o K9o+ Q9o+ JTo+ T9o+",
        25: "33+ A2s+ K3s+ Q4s+ J5s+ T6s+ 96s+ 85s+ 75s+ 64s+ 54s+ A5o+ K9o+ Q9o+ J9o+ T9o+",
    }
    playable = _expand_range(majority_ranges[bucket])
    _set_range(
        result,
        f"Spin 3h BTN · solved-chart majority policy {bucket} BB",
        majority_ranges[bucket],
        playable,
        bucket,
        "solver_majority_summary",
    )
    result["notes"].append(
        f"Profundidade real {depth:g} BB → referência pública mais próxima {bucket} BB. "
        "O conjunto usa mãos abertas em pelo menos 50% das frequências publicadas; abaixo desse limiar "
        "o treinador escolhe FOLD como ação majoritária, sem apagar a existência de mixes menores."
    )

    if c["hand"] not in playable:
        return _fold(result, f"FOLD majoritário na referência {bucket} BB")

    if bucket == 8:
        return _shove(result, depth)

    if bucket == 10:
        premium = _expand_range("TT+ AQs+ AKo")
        if c["hand"] in premium:
            result["notes"].append(
                "A 10 BB o material textual mantém um núcleo premium em min-raise; o restante do conjunto "
                "majoritário é treinado pelo ramo de shove."
            )
            return _raise(result, min(2.0, depth))
        return _shove(result, depth)

    return _raise(result, min(2.0, depth))


def _three_sb(data, c, result, depth):
    _source(result, "sb3")
    situation = data.get("situation", "unopened")
    pressure = str(data.get("preflop_pressure", "none")).lower()

    if situation == "facing_raise":
        if pressure == "allin":
            if depth <= 13:
                calls = _specific("22+ A7o+ A4s+ KTs+ KJo+")
                stack = 11
                notation = "22+ / A7o+ / A4s+ / KTs+ / KJo+"
            else:
                calls = _specific("44+ ATs+ A9o KQo KJs+")
                stack = 25
                notation = "44+ / ATs+ / A9o / KQo / KJs+"
            _set_range(result, "Spin 3h SB vs BTN shove", notation, calls, stack)
            if c["hand"] in calls:
                return _call(result, min(depth, c["stack"]), "Pagar o shove do BTN")
            return _fold(result, "Desistir contra o shove do BTN")

        premium25 = _specific("JJ+ AKs")
        jam25 = _specific(
            _pairs("2", "T"),
            "ATo+ A8s+ KJs+ QTs+ J9s+ T9s+",
        )
        if depth >= 21:
            _set_range(
                result,
                "Spin 3h SB vs BTN min-raise · 25 BB",
                "3-bet 5 BB: JJ+/AKs · shove: 22-TT/ATo+/A8s+/KJs+/QTs+/J9s+/T9s+",
                premium25 | jam25,
                25,
            )
            if c["hand"] in premium25:
                return _raise(result, min(5.0, depth), "3-bet para 5 BB")
            if c["hand"] in jam25:
                return _shove(result, depth)
            return _fold(result, "Fora do núcleo textual de 3-bet/shove")

        jam20 = set(jam25)
        if depth <= 11:
            jam20 |= _expand_range("A7o+ KJo QJo")
        _set_range(
            result,
            "Spin 3h SB vs BTN raise · ≤20 BB",
            "Predominantemente shove/fold; base 25 BB ampliada quando o stack encurta",
            jam20 | _expand_range("KK+"),
            20 if depth > 11 else 10,
            "adapted_published_reference",
        )
        if c["hand"] in _expand_range("KK+") and depth > 11:
            return _raise(result, min(5.0, depth), "3-bet pequeno com núcleo premium")
        if c["hand"] in jam20:
            return _shove(result, depth)
        return _fold(result, "Shove/fold simplificado fora do núcleo publicado")

    if situation != "unopened":
        _set_range(
            result,
            "Spin 3h SB · sequência após ação do BTN",
            "Estratégia mista dependente da sequência completa, sizing e agressor",
            _all_hands(),
            _nearest_standard_depth(depth),
            "mixed_published_strategy",
        )
        result["notes"].append(
            "Limp/re-raise no SB 3-handed é um ramo válido, mas a interface curta ainda não preserva toda a sequência. "
            "A V3.17.1 retorna MISTA em vez de SEM COBERTURA."
        )
        return _mixed(result, "MISTA — sequência completa necessária para escolher raise/call/fold")

    if depth <= 11:
        premium = _expand_range("QQ+ AKs AKo")
        weak_trash = {
            "32o","42o","43o","52o","53o","62o","63o","72o","73o",
            "82o","83o","92o","93o","T2o","T3o","J2o",
        }
        all_hands = _all_hands()
        playable = all_hands - weak_trash
        _set_range(
            result,
            "Spin 3h SB vs BB · ~10 BB simplificado",
            "Premiums min-raise; quase todo o restante do range joga shove; lixo offsuit extremo é fold",
            playable,
            10,
            "study_heuristic_from_published_rules",
        )
        result["notes"].append(
            "A fonte diz que a ~10 BB o SB shova quase todo o range, min-raise premiums e folda lixo. "
            "A separação do lixo offsuit é uma heurística explícita do treinador, não uma cópia do chart GTO."
        )
        if c["hand"] in premium:
            return _raise(result, min(2.0, depth))
        if c["hand"] in playable:
            return _shove(result, depth)
        return _fold(result, "Lixo offsuit extremo no baseline simplificado")

    if depth <= 17:
        shove = _specific(
            _pairs("2", "7"),
            "A2o+ KJo KQo",
            {"76s","87s","98s","T9s","JTs"},
        )
        premium = _expand_range("QQ+ AKs AKo")
        _set_range(
            result,
            "Spin 3h SB vs BB · ~15 BB",
            "Shoves: pares pequenos, maioria dos A offsuit, conectores fortes, KJo/KQo; premiums podem raise",
            shove | premium,
            15,
            "published_text_summary",
        )
        if c["hand"] in premium:
            return _raise(result, min(2.5, depth))
        if c["hand"] in shove:
            return _shove(result, depth)
        result["notes"].append(
            "O chart completo contém limps/raises/shoves mistos para esta classe. "
            "O treinador preserva isso como MISTA em vez de declarar ausência de range."
        )
        return _mixed(result, "MISTA — limp/raise/shove conforme frequência do chart")

    limps = _specific(_pairs("2", "7"), {"KTs","AJs","ATs","AJo","ATo"})
    premiums = _expand_range("JJ+ AQs+ AKo")
    _set_range(
        result,
        "Spin 3h SB vs BB · 22–25 BB · núcleo textual",
        "Limp frequente com pares pequenos/médios e mãos como KTs/AJ/AT; raise maior do SB; range completo é misto",
        limps | premiums,
        25,
        "partial_published_reference",
    )
    if c["hand"] in premiums:
        return _raise(result, 3.0)
    if c["hand"] in limps:
        return _limp(result, "Limp para preservar a faixa de limp-call/limp-shove")
    result["notes"].append(
        "O material público descreve mistura ampla de limp/raise/fold. "
        "Quando a frequência individual não está no resumo textual, a V3.17.1 mantém a classificação MISTA."
    )
    return _mixed(result, "MISTA — limp/raise/fold no SB profundo")


def _all_hands():
    out = set()
    for i, hi in enumerate(RANKS):
        out.add(hi + hi)
        for lo in RANKS[:i]:
            out.add(hi + lo + "s")
            out.add(hi + lo + "o")
    return out


def _three_bb(data, c, result, depth):
    _source(result, "bb3")
    situation = data.get("situation", "unopened")
    pressure = str(data.get("preflop_pressure", "none")).lower()

    if situation == "unopened":
        result.update(
            action="SEM AÇÃO",
            sizing="Você recebeu o pote sem enfrentar ação",
            strategy_status="game_rule",
            profile="Spin 3h BB · todos desistiram",
        )
        return result

    if pressure == "allin":
        if depth <= 11:
            calls = _specific("22+ A3o+ A2s+ K9s+ KTo+ QJo JTs")
            stack = 10
        elif depth <= 18:
            calls = _specific("33+ A4s+ A8o+ JTs+")
            stack = 15
        else:
            calls = _specific("44+ A8s+ ATo+ KQs KQo")
            stack = 25
        _set_range(
            result,
            "Spin 3h BB vs open shove · baseline conservador sem posição do agressor",
            "Interseção conservadora das faixas textuais contra BTN/SB na profundidade mais próxima",
            calls,
            stack,
            "conservative_published_intersection",
        )
        result["notes"].append(
            "A interface rápida não informa se o shove veio do BTN ou SB. Para não superestimar calls, "
            "o motor usa um núcleo conservador comum às referências publicadas."
        )
        if c["hand"] in calls:
            return _call(result, min(depth, c["stack"]), "Pagar o open shove")
        return _fold(result, "Desistir contra o open shove no baseline conservador")

    if situation == "limped":
        if depth <= 7:
            result["notes"].append("A 7 BB ou menos a fonte recomenda trabalhar entre shove e check sobre limp.")
            strong = _specific("22+ A2s+ A2o+ K2s+ K6o+ Q8s+ JTs")
            _set_range(result, "Spin 3h BB vs SB limp · ≤7 BB", "Núcleo de shove curto", strong, 7, "study_heuristic")
            if c["hand"] in strong:
                return _shove(result, depth)
            result.update(action="CHECK", sizing="Dar check e ver o flop")
            return result
        size = 3.0 if depth >= 20 else 2.5 if depth >= 10 else 2.0
        strong = _expand_range("99+ AJs+ KTs+")
        _set_range(
            result,
            "Spin 3h BB vs SB limp · sizing publicado",
            f"Raise sobre limp: {size:g} BB nesta profundidade; núcleo forte 99+/AJs+/KTs+",
            strong,
            25 if depth >= 20 else 15 if depth >= 10 else 7,
            "published_sizing_partial_range",
        )
        if c["hand"] in strong:
            return _raise(result, min(size, depth))
        result.update(action="CHECK", sizing="Dar check; faixa média joga pós-flop em posição")
        return result

    if situation != "facing_raise":
        _set_range(
            result,
            "Spin 3h BB · sequência avançada",
            "Ramo misto dependente da sequência exata",
            _all_hands(),
            _nearest_standard_depth(depth),
            "mixed_published_strategy",
        )
        result["notes"].append(
            "Re-raise/4-bet no BB exige saber a sequência e o agressor. "
            "A V3.17.1 sinaliza MISTA, nunca SEM COBERTURA para um estado pré-flop válido."
        )
        return _mixed(result, "MISTA — sequência/agressor necessários")

    premium = _expand_range("JJ+ AJs+")
    reshove25 = _specific("22+ ATo+ KQo")
    if depth >= 20:
        _set_range(
            result,
            "Spin 3h BB vs raise · 25 BB",
            "Jogar por stacks: 22+/AT+/KQ+; defesa muito ampla em calls",
            reshove25 | premium,
            25,
        )
        if c["hand"] in premium:
            return _raise(result, min(7.5, depth), "3-bet de valor ~7,5 BB no baseline")
        if c["hand"] in reshove25:
            return _shove(result, depth)
        if _all_suited(c["hand"]) or _offsuit_at_least(c["hand"], "K", "2") or _offsuit_at_least(c["hand"], "Q", "4") or _offsuit_at_least(c["hand"], "J", "6") or _offsuit_at_least(c["hand"], "T", "7"):
            result.update(action="CALL", sizing="Defender o BB; range publicado é muito amplo")
            return result
        return _fold(result, "Parte offsuit mais fraca da defesa 25 BB")

    if depth <= 11:
        shove = _specific("22+ A2s+ A2o+ KJs KJo KQs KQo Q9s+")
        _set_range(
            result,
            "Spin 3h BB vs BTN/SB raise · ~10 BB",
            "Shove: qualquer par, quase qualquer A, KJ+ e alguns K/Q suited",
            shove,
            10,
            "adapted_published_reference",
        )
        if c["hand"] in shove:
            return _shove(result, depth)
        result["notes"].append(
            "Calls marginais dependem da posição do raiser e do chart completo; esta classe permanece estratégia mista."
        )
        return _mixed(result, "MISTA — call/fold depende do raiser")

    shove15 = _specific(_pairs("2", "J"), "A8o+ A2s A3s A4s A5s", {"87s","98s","T9s","JTs"})
    premium15 = _expand_range("QQ+ AKs")
    _set_range(
        result,
        "Spin 3h BB vs raise · ~15 BB",
        "Shove amplo: pares até JJ, A8o+, alguns A suited baixos e conectores; premium 3-bet",
        shove15 | premium15,
        15,
        "published_text_summary",
    )
    if c["hand"] in premium15:
        return _raise(result, min(5.0, depth), "3-bet pequeno com premium")
    if c["hand"] in shove15:
        return _shove(result, depth)
    if _all_suited(c["hand"]):
        result.update(action="CALL", sizing="Defender suited; a fonte mantém todos os suited na defesa ~15 BB")
        return result
    return _fold(result, "Fora do baseline textual de defesa")


def _hu_button(data, c, result, depth):
    _source(result, "hubtn")
    if data.get("situation", "unopened") != "unopened":
        _set_range(
            result,
            "Spin HU BTN · reação após ação do BB",
            "Estratégia mista dependente da linha limp/raise e sizing",
            _all_hands(),
            _nearest_standard_depth(depth),
            "mixed_published_strategy",
        )
        result["notes"].append(
            "Reações HU após limp/min-raise dependem da linha anterior. A V3.17.1 mantém MISTA "
            "quando a interface não fornece a sequência completa."
        )
        return _mixed(result, "MISTA — reação HU depende da linha anterior")

    if depth <= 11:
        shove = _specific(
            _pairs("2", "4"),
            "A2o+ K5o+",
            {"K2s","K3s","K4s","65s","76s","87s","98s","T9s"},
        )
        traps = _specific(_pairs("5", "A"), "A7s+")
        _set_range(
            result,
            "Spin HU BTN · 10 BB",
            "Shove: 22-44/A2o+/K5o+/K2s-K4s + alguns conectores; muitos limps/traps permanecem",
            shove | traps,
            10,
        )
        if c["hand"] in shove:
            return _shove(result, depth)
        result["notes"].append(
            "A fonte mantém muitos limps mesmo a 10 BB, inclusive pares médios/premiums e A7s-AKs."
        )
        return _limp(result, "Limp; preservar limp-call/limp-shove e jogar em posição")

    if depth <= 16:
        shove = _specific(_pairs("2", "5"), {"A2o","A3o","A4o","A5o","A6o","A7o"})
        minraise = _specific("TT+ KJs A8s+")
        _set_range(
            result,
            "Spin HU BTN · 13–15 BB",
            "Open-shove cresce com pares pequenos e A offsuit fracos/médios; TT/JJ/KJs/A8s+ podem min-raise; maioria ainda limpa",
            shove | minraise,
            14,
            "published_text_summary",
        )
        if c["hand"] in shove:
            return _shove(result, depth)
        if c["hand"] in minraise:
            return _raise(result, 2.0)
        return _limp(result, "Limp; maioria do range HU continua em limp a 13–15 BB")

    trash = {"32o","42o","43o","52o","53o","62o","63o","72o","73o","82o","83o"}
    premium = _expand_range("QQ+ AKs AKo")
    playable = _all_hands() - trash
    _set_range(
        result,
        "Spin HU BTN · 20–25 BB",
        "Pouquíssimos folds; muitos limps; raises 2 BB; premiums/high suited aces balanceiam steals",
        playable,
        25,
        "published_text_summary",
    )
    if c["hand"] in trash:
        return _fold(result, "Trash offsuit do extremo inferior do range HU")
    if c["hand"] in premium:
        return _raise(result, 2.0)
    return _limp(result, "Limp; o HU profundo de Spin usa uma faixa muito ampla de limps")


def _hu_bb_call_vs_shove(c, result, depth):
    _source(result, "hubb")
    if depth <= 11:
        calls = _specific("22+ A2s+ K9o+ K7s+ JTo JTs J9s")
        stack = 10
        notation = "22+/A2s+/K9o+/K7s+/JTo+/J9s+"
    elif depth <= 16:
        calls = _specific("22+ A2o+ K6o+ K3s+ Q9o+ Q7s+ 98s+")
        stack = 13
        notation = "22+/A2o+/K6o+/K3s+/Q9o+/Q7s+/98s+"
    else:
        calls = _specific("44+ ATo+ KQo QJs+")
        stack = 25
        notation = "44+/ATo+/KQo+/QJs+"
    _set_range(result, "Spin HU BB vs BTN open shove", notation, calls, stack)
    if c["hand"] in calls:
        return _call(result, min(depth, c["stack"]), "Pagar o open shove do BTN")
    return _fold(result, "Fora da faixa textual de call vs shove")


def _hu_bb(data, c, result, depth):
    _source(result, "hubb")
    situation = data.get("situation", "unopened")
    pressure = str(data.get("preflop_pressure", "none")).lower()

    if situation == "unopened":
        result.update(
            action="SEM AÇÃO",
            sizing="BTN desistiu; pote encerrado",
            strategy_status="game_rule",
            profile="Spin HU BB · sem ação",
        )
        return result

    if situation == "facing_raise" and pressure == "allin":
        return _hu_bb_call_vs_shove(c, result, depth)

    if situation == "limped":
        if depth >= 20:
            iso = _expand_range("99+ AJs+ KTs+")
            shove = _specific(_pairs("2", "8"), "A2o+", {"76s","87s","98s","T9s"})
            _set_range(
                result,
                "Spin HU BB vs BTN limp · 20–25 BB",
                "Iso 3,5 BB: 99+/AJs+/KTs+ · shove: A offsuit, pares pequenos/médios e alguns conectores",
                iso | shove,
                25,
            )
            if c["hand"] in iso:
                return _raise(result, 3.5, "Iso-raise para 3,5 BB")
            if c["hand"] in shove:
                return _shove(result, depth)
            result.update(action="CHECK", sizing="Dar check e jogar pós-flop")
            return result

        if depth >= 12:
            iso = _expand_range("99+ A9s+ K9s+")
            shove = _specific(
                "A2o+ A2s+",
                {"K2s","K3s","K4s","K5s","K6s","K7s","K8s","K7o","K8o","K9o","Q5s","Q6s","Q7s","76s","87s","98s","T9s"},
            )
            _set_range(
                result,
                "Spin HU BB vs BTN limp · 12–14 BB",
                "Iso 2,5 BB: pares fortes/A9s+/K9s+ · shove cresce com A, K baixos, Q suited baixas e conectores",
                iso | shove,
                13,
                "adapted_published_reference",
            )
            if c["hand"] in iso:
                return _raise(result, 2.5, "Iso-raise para 2,5 BB")
            if c["hand"] in shove:
                return _shove(result, depth)
            result.update(action="CHECK", sizing="Dar check e realizar equidade")
            return result

        iso = _expand_range("99+ A9s+")
        shove = _specific("A2o+ A2s+ K2o+ K2s+ 22+")
        _set_range(
            result,
            "Spin HU BB vs BTN limp · 10–11 BB",
            "Shove muito amplo; qualquer K offsuit entra no núcleo descrito",
            iso | shove,
            10,
            "adapted_published_reference",
        )
        if c["hand"] in iso:
            return _raise(result, min(2.5, depth), "Iso pequeno com topo da faixa")
        if c["hand"] in shove:
            return _shove(result, depth)
        result.update(action="CHECK", sizing="Dar check")
        return result

    if situation != "facing_raise":
        _set_range(
            result,
            "Spin HU BB · sequência avançada",
            "Estratégia mista dependente da linha anterior e sizing",
            _all_hands(),
            _nearest_standard_depth(depth),
            "mixed_published_strategy",
        )
        result["notes"].append(
            "Re-raise HU exige a linha anterior completa. A V3.17.1 sinaliza MISTA em vez de SEM COBERTURA."
        )
        return _mixed(result, "MISTA — sequência HU completa necessária")

    if depth >= 20:
        nonallin = _expand_range("TT+ AJs+")
        shove = _specific(
            _pairs("2", "9"),
            "A2o+",
            {"A8s","A9s","ATs","KQo","76s","87s","98s","T9s"},
        )
        _set_range(
            result,
            "Spin HU BB vs min-raise · 21–25 BB",
            "3-bet não all-in: TT+/AJs+ · shove: 22-99/A2o+/A8s-ATs/KQo + conectores · call muito amplo",
            nonallin | shove,
            25,
        )
        if c["hand"] in nonallin:
            return _raise(result, 5.0, "3-bet pequeno para ~5 BB (simplificação de sizing)")
        if c["hand"] in shove:
            return _shove(result, depth)
        if _all_suited(c["hand"]) or _offsuit_at_least(c["hand"], "K", "2") or _offsuit_at_least(c["hand"], "Q", "2") or _offsuit_at_least(c["hand"], "J", "6"):
            result.update(action="CALL", sizing="Defender muito amplo contra min-raise 2 BB")
            return result
        return _fold(result, "Extremo inferior offsuit da defesa HU")

    if depth >= 12:
        traps = {"AA", "KK"}
        shove = _specific(_pairs("2", "Q"), "A2o+ A2s+ KTo+")
        _set_range(
            result,
            "Spin HU BB vs min-raise · 12–14 BB",
            "Sem 3-bet pequeno: shove 22-QQ/A2o+/A2s+/KTo+ + extensões; AA/KK podem trap-call",
            shove | traps,
            13,
        )
        if c["hand"] in traps:
            result.update(action="CALL", sizing="Flat/trap com premium")
            return result
        if c["hand"] in shove:
            return _shove(result, depth)
        if _all_suited(c["hand"]):
            result.update(action="CALL", sizing="Defender suited; faixa de call segue muito ampla")
            return result
        result["notes"].append(
            "Offsuit marginal depende do chart completo; a estratégia é preservada como mista."
        )
        return _mixed(result, "MISTA — call/fold em frequência")

    traps = {"AA", "KK"}
    shove = _specific("22+ A2o+ A2s+ K2o+ K2s+ Q8s+")
    _set_range(
        result,
        "Spin HU BB vs min-raise · 10–11 BB",
        "Shove: qualquer A, qualquer K, qualquer par + algumas Q suited/conectores; AA/KK podem trap",
        shove | traps,
        10,
        "adapted_published_reference",
    )
    if c["hand"] in traps:
        result.update(action="CALL", sizing="Flat/trap com AA/KK")
        return result
    if c["hand"] in shove:
        return _shove(result, depth)
    result.update(action="CALL", sizing="Flat amplo com stack curto; fold apenas parte mais fraca")
    return result


def decide_spin(data, c, result, postflop):
    """Return a Spin-specific study decision.

    The caller already validated cards, position and completed_hand.
    """
    if c["players"] not in {2, 3}:
        _source(result, "rules", "course")
        result["profile"] = "Spin & Go · formato incompatível"
        result["notes"].append(
            "O Spin & Go padrão estudado aqui começa 3-handed e passa para heads-up. "
            "Selecione 3 jogadores ou 2 quando um oponente for eliminado."
        )
        return result

    depth = _spin_header(result, c)
    street = data.get("street", "preflop")
    if street != "preflop":
        result = postflop(data, c, result)
        result["profile"] = "Spin & Go · " + result["profile"]
        result["notes"].insert(
            0,
            f"Camada Spin pós-flop: {c['players']}-handed, {depth:g} BB efetivos. "
            "A V3.17.1 reutiliza a heurística de força/textura/pot odds; ranges multiway e frequências de solver ainda não são reproduzidos."
        )
        _source(result, "course", "gto")
        result["strategy_status"] = "spin_postflop_heuristic"
        return result

    if depth > 33:
        result["notes"].append(
            "A biblioteca Spin pesquisada concentra soluções até a faixa baixa de 30 BB. "
            "Acima disso o motor não extrapola automaticamente."
        )
        _source(result, "gto")
        return result

    if c["players"] == 3:
        if c["position"] == "BTN":
            return _three_btn(data, c, result, depth)
        if c["position"] == "SB":
            return _three_sb(data, c, result, depth)
        if c["position"] == "BB":
            return _three_bb(data, c, result, depth)
    else:
        if c["position"] == "BTN/SB":
            return _hu_button(data, c, result, depth)
        if c["position"] == "BB":
            return _hu_bb(data, c, result, depth)

    result["notes"].append("Posição Spin não reconhecida para a quantidade atual de jogadores.")
    return result
