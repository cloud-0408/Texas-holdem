#!/usr/bin/env python3
import bisect
import itertools
import json
import random
import sys

KEEP_RUNNING = ">>>BOTZONE_REQUEST_KEEP_RUNNING<<<"

N_PLAYERS = 2
INITIAL_CHIPS = 20000
SMALL_BLIND = 50
BIG_BLIND = 100
TOTAL_HANDS = 70                 # ★改：50 → 70
LOCK_WIN_MARGIN = 1500
HAND_CLASS_SCORE = [0.08, 0.22, 0.40, 0.58, 0.69, 0.76, 0.84, 0.93, 0.98]
SIMS = {0: 480, 3: 640, 4: 820, 5: 0}
EXTRA_SIMS = {0: 180, 3: 200, 4: 160}

PRESETS = {
    "BALANCED": {"thr": 0.00, "bluff_ff": 0.52, "gate": 0.28, "size": 0.00, "widen": 0.00},
    "TIGHT":    {"thr": 0.04, "bluff_ff": 0.60, "gate": 0.35, "size": -0.03, "widen": -0.03},
    "AGGRO":    {"thr": -0.05, "bluff_ff": 0.44, "gate": 0.20, "size": 0.05, "widen": 0.05},
    "VALUE":    {"thr": -0.02, "bluff_ff": 0.85, "gate": 0.60, "size": 0.06, "widen": 0.04},
}

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def card_suit(c):
    return c % 4

def card_number(c):
    return c // 4 + 2

def next_player(p, off):
    return (p + off) % N_PLAYERS

# ═══════════════ 翻前 169 手查表 ═══════════════
PREFLOP_TABLE = {}
_base = {
    (14, 14): 1.00, (13, 13): 0.95, (12, 12): 0.90, (11, 11): 0.86, (10, 10): 0.82,
    (9, 9): 0.78, (8, 8): 0.74, (7, 7): 0.70, (6, 6): 0.66, (5, 5): 0.62,
    (4, 4): 0.58, (3, 3): 0.55, (2, 2): 0.52,
    (14, 13): 0.68, (14, 12): 0.65, (14, 11): 0.62, (14, 10): 0.59, (14, 9): 0.54,
    (14, 8): 0.48, (14, 7): 0.44, (14, 6): 0.41, (14, 5): 0.38, (14, 4): 0.36,
    (14, 3): 0.35, (14, 2): 0.34,
    (13, 12): 0.58, (13, 11): 0.55, (13, 10): 0.52, (13, 9): 0.47, (13, 8): 0.42,
    (13, 7): 0.39, (13, 6): 0.36, (13, 5): 0.34, (13, 4): 0.32, (13, 3): 0.31, (13, 2): 0.30,
    (12, 11): 0.51, (12, 10): 0.48, (12, 9): 0.43, (12, 8): 0.38, (12, 7): 0.36,
    (12, 6): 0.33, (12, 5): 0.31, (12, 4): 0.30, (12, 3): 0.29, (12, 2): 0.28,
    (11, 10): 0.45, (11, 9): 0.40, (11, 8): 0.36, (11, 7): 0.34, (11, 6): 0.31,
    (11, 5): 0.29, (11, 4): 0.28, (11, 3): 0.27, (11, 2): 0.26,
    (10, 9): 0.38, (10, 8): 0.34, (10, 7): 0.32, (10, 6): 0.29, (10, 5): 0.27,
    (10, 4): 0.26, (10, 3): 0.25, (10, 2): 0.24,
    (9, 8): 0.32, (9, 7): 0.30, (9, 6): 0.27, (9, 5): 0.25, (9, 4): 0.24, (9, 3): 0.23, (9, 2): 0.22,
    (8, 7): 0.29, (8, 6): 0.26, (8, 5): 0.24, (8, 4): 0.23, (8, 3): 0.22, (8, 2): 0.21,
    (7, 6): 0.25, (7, 5): 0.23, (7, 4): 0.22, (7, 3): 0.21, (7, 2): 0.20,
    (6, 5): 0.22, (6, 4): 0.21, (6, 3): 0.20, (6, 2): 0.19,
    (5, 4): 0.21, (5, 3): 0.20, (5, 2): 0.19, (4, 3): 0.19, (4, 2): 0.18, (3, 2): 0.17,
}
for (_h, _l), _v in _base.items():
    if _h == _l:
        PREFLOP_TABLE[(_h, _l, False)] = _v
    else:
        s = min(1.0, _v + 0.04)
        o = max(0.0, _v - 0.02)
        if _h - _l == 1:
            s, o = min(1.0, _v + 0.06), _v
        elif _h - _l == 2:
            s = min(1.0, _v + 0.05)
        if _h == 14 and _l >= 10:
            s, o = min(1.0, _v + 0.06), min(1.0, _v + 0.02)
        PREFLOP_TABLE[(_h, _l, True)] = s
        PREFLOP_TABLE[(_h, _l, False)] = o

def preflop_strength(cards):
    r1, r2 = card_number(cards[0]), card_number(cards[1])
    hi, lo = max(r1, r2), min(r1, r2)
    suited = card_suit(cards[0]) == card_suit(cards[1])
    v = PREFLOP_TABLE.get((hi, lo, suited and hi != lo))
    if v is not None:
        return v
    gap = hi - lo
    score = (hi - 2) / 16.0 + (lo - 2) / 28.0
    if r1 == r2:
        score += 0.25 + (hi - 2) / 30.0
    else:
        if suited:
            score += 0.06
        if gap == 1:
            score += 0.06
        elif gap == 2:
            score += 0.03
        elif gap >= 4:
            score -= 0.04
    if hi == 14:
        score += 0.04
        if lo >= 10:
            score += 0.04
    return clamp(score, 0.0, 1.0)

def preflop_class(cards):
    r = sorted((card_number(c) for c in cards), reverse=True)
    return {"high": r[0], "low": r[1],
            "suited": card_suit(cards[0]) == card_suit(cards[1]), "pair": r[0] == r[1]}

def is_3bet_candidate(cards):
    p = preflop_class(cards)
    return p["pair"] or (p["high"] == 14 and p["low"] >= 12)

def is_trash(cards, st=None):
    p = preflop_class(cards)
    if p["pair"]:
        return False
    hi, lo, gap, suited = p["high"], p["low"], p["high"] - p["low"], p["suited"]
    st = preflop_strength(cards) if st is None else st
    if hi == 14:
        return False
    if suited and gap <= 2 and hi >= 6:
        return False
    if hi >= 11 and lo >= 8 and gap <= 4:
        return False
    if st <= 0.30:
        return True
    if not suited and hi <= 10 and lo <= 5 and gap >= 3:
        return True
    if suited and hi <= 9 and lo <= 4 and gap >= 4:
        return True
    return False

# ═══════════════ 牌力评估（含轮子 A2345）═══════════════
def evaluate_5(cards):
    ranks = sorted((card_number(c) for c in cards), reverse=True)
    suits = [card_suit(c) for c in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(((c, r) for r, c in cnt.items()), reverse=True)
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight, hi = False, 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight, hi = True, uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight, hi = True, 5
    if flush and straight:
        return (8, hi)
    if groups[0][0] == 4:
        return (7, groups[0][1], max(r for r in ranks if r != groups[0][1]))
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, hi)
    if groups[0][0] == 3:
        t = groups[0][1]
        return (3, t, *sorted((r for r in ranks if r != t), reverse=True))
    if groups[0][0] == 2 and groups[1][0] == 2:
        hp, lp = max(groups[0][1], groups[1][1]), min(groups[0][1], groups[1][1])
        return (2, hp, lp, max(r for r in ranks if r not in (hp, lp)))
    if groups[0][0] == 2:
        p = groups[0][1]
        return (1, p, *sorted((r for r in ranks if r != p), reverse=True))
    return (0, *ranks)

def evaluate_best(cards):
    if len(cards) <= 5:
        if len(cards) == 5:
            return evaluate_5(cards)
        return (0, *sorted((card_number(c) for c in cards), reverse=True))
    best = None
    for combo in itertools.combinations(cards, 5):
        s = evaluate_5(combo)
        if best is None or s > best:
            best = s
    return best

def made_metric(hole, public):
    if len(public) < 3:
        return 0.0
    s = evaluate_best(hole + public)
    m = HAND_CLASS_SCORE[s[0]]
    detail = sum(r / (16.0 * (2 ** i)) for i, r in enumerate(s[1:4]))
    return clamp(m + detail * 0.008, 0.0, 0.995)

# ═══════════════ 结构分析 ═══════════════
def board_texture(public):
    info = {"wet": 0.0, "flush_p": 0.0, "straight_p": 0.0,
            "paired": False, "high": 0, "dynamic": False}
    if len(public) < 3:
        return info
    ranks = [card_number(c) for c in public]
    suits = [card_suit(c) for c in public]
    info["high"] = max(ranks)
    info["paired"] = len(set(ranks)) < len(ranks)
    sc = {}
    for s in suits:
        sc[s] = sc.get(s, 0) + 1
    m = max(sc.values())
    info["flush_p"] = 1.0 if m >= 4 else 0.75 if m == 3 else (0.35 if m == 2 and len(public) >= 4 else 0.0)
    exp = set(ranks)
    if 14 in exp:
        exp.add(1)
    sp = 0.0
    for st in range(1, 11):
        w = set(range(st, st + 5))
        pr = len(exp & w)
        if pr >= 4:
            sp = max(sp, 1.0)
        elif pr == 3:
            sp = max(sp, 0.65)
    info["straight_p"] = sp
    wet = 0.18 * info["flush_p"] + 0.22 * sp
    if info["high"] >= 12:
        wet += 0.03
    if len(public) >= 4 and not info["paired"]:
        wet += 0.04
    if info["paired"]:
        wet -= 0.06
    info["wet"] = clamp(wet, 0.0, 1.0)
    info["dynamic"] = info["flush_p"] >= 0.75 or sp >= 0.65 or info["wet"] >= 0.45
    return info

def pair_profile(hole, public):
    info = {"made_class": -1, "pair_rank": None, "pair_type": "none",
            "kicker_rank": 0, "board_overcards": 0, "weak_kicker": False}
    if len(public) < 3:
        return info
    s = evaluate_best(hole + public)
    info["made_class"] = s[0]
    if s[0] != 1:
        return info
    pr = s[1]
    hr = [card_number(c) for c in hole]
    br = [card_number(c) for c in public]
    bu = sorted(set(br), reverse=True)
    info["pair_rank"] = pr
    info["board_overcards"] = sum(1 for r in set(br) if r > pr)
    kick = [r for r in hr if r != pr]
    info["kicker_rank"] = max(kick) if kick else max((r for r in br if r != pr), default=0)
    info["weak_kicker"] = info["kicker_rank"] <= 9
    if pr not in hr:
        info["pair_type"] = "board_pair"
    elif hr[0] == hr[1] and hr[0] == pr:
        if br and pr > max(br):
            info["pair_type"] = "overpair"
        elif info["board_overcards"] >= 1:
            info["pair_type"] = "underpair"
        else:
            info["pair_type"] = "pocket_pair"
    elif bu and pr == bu[0]:
        info["pair_type"] = "top_pair"
    elif len(bu) >= 2 and pr == bu[1]:
        info["pair_type"] = "middle_pair"
    else:
        info["pair_type"] = "bottom_pair"
    return info

def draw_profile(hole, public):
    info = {"quality": 0.0, "type": "none", "flush": False, "nut_flush": False,
            "near_nut_flush": False, "straight": "none", "combo": False,
            "overcards": 0, "semi": False, "ftd": 0.0, "sbonus": 0.0}
    if len(public) < 3 or len(public) >= 5:
        return info
    cards = hole + public
    hr = [card_number(c) for c in hole]
    bh = max(card_number(c) for c in public)
    info["overcards"] = sum(1 for r in hr if r > bh)
    sc = {}
    for c in cards:
        sc[card_suit(c)] = sc.get(card_suit(c), 0) + 1
    fq = 0.0
    for s, cn in sc.items():
        if cn != 4:
            continue
        hfr = sorted((card_number(c) for c in hole if card_suit(c) == s), reverse=True)
        if not hfr:
            continue
        bfr = [card_number(c) for c in public if card_suit(c) == s]
        high = max(hfr)
        seen = set(hfr + bfr)
        better = len([r for r in range(high + 1, 15) if r not in seen])
        nut = better == 0
        info["flush"] = True
        info["nut_flush"] = info["nut_flush"] or nut
        cand = 0.21 if nut else 0.16
        if not nut and high >= 12 and better <= 1:
            cand = max(cand, 0.185)
            info["near_nut_flush"] = True
        if high <= 9:
            cand -= 0.025
        fq = max(fq, cand)
    ranks = set(card_number(c) for c in cards)
    exp = set(ranks)
    if 14 in exp:
        exp.add(1)
    hexp = set(hr)
    if 14 in hexp:
        hexp.add(1)
    sq, gut, oesd = 0.0, 0, False
    for st in range(1, 11):
        w = set(range(st, st + 5))
        pres = exp & w
        if len(pres) != 4 or not (hexp & pres):
            continue
        miss = next(iter(w - pres))
        if miss in (st, st + 4):
            oesd = True
            sq = max(sq, 0.17)
        else:
            gut += 1
            sq = max(sq, 0.10)
    if oesd:
        info["straight"] = "open_ended"
    elif gut >= 2:
        info["straight"] = "double_gutshot"
        sq = max(sq, 0.13)
    elif gut:
        info["straight"] = "gutshot"
    info["combo"] = info["flush"] and info["straight"] != "none"
    q = max(fq, sq)
    if info["combo"]:
        q = max(q, fq + sq + 0.04)
        info["type"] = "combo"
        info["ftd"], info["sbonus"] = 0.07, 0.06
    elif info["nut_flush"]:
        info["type"] = "nut_flush"
        info["ftd"], info["sbonus"] = 0.05, 0.04
    elif info["flush"]:
        info["type"] = "flush"
        info["ftd"], info["sbonus"] = (0.04, 0.035) if info["near_nut_flush"] else (0.01, 0.02)
    elif info["straight"] == "open_ended":
        info["type"] = "oesd"
        info["ftd"], info["sbonus"] = 0.03, 0.02
    elif info["straight"] == "double_gutshot":
        info["type"] = "double_gutshot"
        info["ftd"], info["sbonus"] = 0.02, 0.01
    elif info["straight"] == "gutshot":
        info["type"] = "gutshot"
        info["ftd"], info["sbonus"] = -0.03, -0.02
    if len(public) == 3:
        q += 0.025 * info["overcards"]
    info["quality"] = clamp(q, 0.0, 0.35)
    info["semi"] = (info["combo"] or info["nut_flush"]
                    or info["straight"] in ("open_ended", "double_gutshot")
                    or (info["flush"] and info["quality"] >= 0.16)
                    or (info["straight"] == "gutshot" and info["overcards"] >= 1 and info["quality"] >= 0.13))
    return info

def value_tier(hole, public, pp, tex):
    if len(public) < 3:
        return {"tier": "none", "sbonus": 0.0}
    full = evaluate_best(hole + public)
    cls = full[0]
    wet = tex["wet"]
    hr = [card_number(c) for c in hole]
    if cls >= 6:
        return {"tier": "nut", "sbonus": 0.22 + 0.08 * wet}
    if cls == 5:
        return {"tier": "strong", "sbonus": 0.15 + 0.06 * wet}
    if cls == 4:
        return {"tier": "strong", "sbonus": 0.12 + 0.05 * wet}
    if cls == 3:
        setm = hr.count(full[1]) == 2
        t = "nut" if setm and tex["dynamic"] else "strong"
        return {"tier": t, "sbonus": 0.20 if t == "nut" else 0.13 + 0.05 * wet}
    if cls == 2:
        if tex["paired"]:
            return {"tier": "thin", "sbonus": 0.0}
        return {"tier": "strong", "sbonus": 0.10 + 0.06 * wet}
    if cls == 1 and pp["made_class"] == 1:
        pt = pp["pair_type"]
        if pt == "overpair":
            return {"tier": "strong", "sbonus": 0.13 + 0.07 * wet}
        if pt == "top_pair":
            if pp["weak_kicker"]:
                return {"tier": "thin", "sbonus": 0.01 - 0.03 * wet}
            t = "strong" if pp["pair_rank"] >= 11 else "thin"
            return {"tier": t, "sbonus": 0.09 + 0.03 * wet if t == "strong" else 0.02}
        return {"tier": "thin", "sbonus": -0.02 * wet}
    return {"tier": "none", "sbonus": 0.0}

def nutted_risk(hole, public, tex):
    if len(public) < 3:
        return 0.0
    cls = evaluate_best(hole + public)[0]
    r = 0.0
    if cls == 5 and tex["paired"]:
        r += 0.05
    elif cls == 4 and (tex["flush_p"] >= 0.75 or tex["paired"]):
        r += 0.04
    elif cls == 3 and tex["paired"]:
        r += 0.04
    elif cls == 2 and tex["paired"]:
        r += 0.06
    elif cls == 1 and tex["flush_p"] >= 1.0:
        r += 0.03
    return clamp(r, 0.0, 0.14)

# ═══════════════ 状态重建（★盲注：SB=dealer）═══════════════
def reconstruct(req):
    my_id = req["my_id"]
    dealer = req["dealer_id"]
    stacks = [INITIAL_CHIPS] * 2
    committed = [0, 0]
    sb = dealer                       # ★修复：庄家=小盲
    bb = next_player(dealer, 1)       # ★非庄家=大盲
    stacks[sb] -= SMALL_BLIND
    stacks[bb] -= BIG_BLIND
    committed[sb] += SMALL_BLIND
    committed[bb] += BIG_BLIND
    cur = 0
    round_bet = BIG_BLIND
    round_raise = 2 * BIG_BLIND
    contrib = [0, 0]
    contrib[sb], contrib[bb] = SMALL_BLIND, BIG_BLIND
    alive = [True, True]
    allin = [False, False]
    for rec in req.get("history", []):
        rr, pid, act, at = rec["round"], rec["player_id"], rec["action"], rec["action_type"]
        if rr != cur:
            cur, round_bet, round_raise, contrib = rr, 0, BIG_BLIND, [0, 0]
        if at == "fold":
            alive[pid] = False
            continue
        if not alive[pid] or allin[pid]:
            continue
        if at == "allin":
            add = stacks[pid]
            stacks[pid] = 0
            committed[pid] += add
            contrib[pid] += add
            allin[pid] = True
            round_bet = max(round_bet, contrib[pid])
        elif at in ("call", "check"):
            need = min(max(0, round_bet - contrib[pid]), stacks[pid])
            stacks[pid] -= need
            committed[pid] += need
            contrib[pid] += need
        elif at == "raise":
            add = max(0, min(act, stacks[pid]))
            stacks[pid] -= add
            committed[pid] += add
            contrib[pid] += add
            round_bet = max(round_bet, contrib[pid])
            round_raise = max(round_raise, 2 * add)
    pc = len(req["public_cards"])
    ridx = 0 if pc == 0 else 1 if pc == 3 else 2 if pc == 4 else 3
    if cur != ridx:
        round_bet, round_raise, contrib = 0, BIG_BLIND, [0, 0]
    opp = next_player(my_id, 1)
    my_rb = contrib[my_id]
    to_call = max(0, round_bet - my_rb)
    allin_call = max(0, min(committed[opp], committed[my_id] + stacks[my_id]) - committed[my_id])
    return {"round": ridx, "round_bet": round_bet, "round_raise": round_raise,
            "my_round_bet": my_rb, "pot": committed[0] + committed[1], "to_call": to_call,
            "opp_allin": allin[opp] and alive[opp], "allin_call": allin_call,
            "stacks": stacks, "committed": committed}

# ═══════════════ 锁定 / 反锁死 ═══════════════
def remaining_hands(req):
    if "hand" in req and "max_hand" in req:
        try:
            return max(0, int(req["max_hand"]) - int(req["hand"]))
        except (TypeError, ValueError):
            pass
    return None

def hand_index(req):
    for k in ("hand", "hand_id", "round_id"):
        if k in req:
            try:
                return int(req[k])
            except (TypeError, ValueError):
                pass
    return None

def forced_loss(req, committed_me, my_id, rh):
    if rh is None or rh <= 0:
        return None
    loss = committed_me
    d = req["dealer_id"]
    for off in range(1, rh):
        fd = next_player(d, off)
        # SB=fd, BB=非fd
        if my_id == fd:
            loss += SMALL_BLIND
        else:
            loss += BIG_BLIND
    return loss

def should_lock(req, state, my_id):
    tw = req.get("total_win_chips", [0, 0])
    if len(tw) <= my_id:
        return False
    try:
        lead = int(tw[my_id])
    except (TypeError, ValueError):
        return False
    rh = remaining_hands(req)
    fl = forced_loss(req, state["committed"][my_id], my_id, rh)
    return lead >= LOCK_WIN_MARGIN if fl is None else lead > fl

def fold_gives_opp_lock(req, state, my_id):
    opp = next_player(my_id, 1)
    tw = req.get("total_win_chips", [0, 0])
    if len(tw) <= opp:
        return False
    rh = remaining_hands(req)
    if rh is None or rh <= 1:
        return False
    try:
        lead = int(tw[opp])
    except (TypeError, ValueError):
        return False
    after = lead + state["committed"][my_id]
    fl = forced_loss(req, state["committed"][opp], opp, rh)
    if fl is None:
        return after >= LOCK_WIN_MARGIN
    return after > max(0, fl - state["committed"][opp])

# ═══════════════ 对手建模 + 漂移 + 自适应 ═══════════════
def latest_by_hand(requests):
    latest, fb = {}, TOTAL_HANDS
    for req in requests:
        h = hand_index(req)
        if h is None:
            h, fb = fb, fb + 1
        p = latest.get(h)
        if p is None or len(req.get("history", [])) >= len(p.get("history", [])):
            latest[h] = req
    return [latest[h] for h in sorted(latest)]

def smooth(s, t, pr, w):
    return (s + pr * w) / (t + w)

def track_hand(req, my_id, opp):
    st = {"pf_opp": 0, "vol": 0, "pfr": 0, "total": 0, "aggr": 0, "allin": 0,
          "post": 0, "post_aggr": 0, "post_check": 0, "ftr_opp": 0, "ftr": 0,
          "cbet_opp": 0, "cbet": 0, "ftcb_opp": 0, "ftcb": 0}
    hist = req.get("history", [])
    if not hist:
        return st
    seen_pf = my_pressure = opp_pf_raised = False
    opp_first_flop = my_first_flop = True
    opp_cbet_this = False
    for rec in hist:
        pid, at, r = rec["player_id"], rec["action_type"], rec["round"]
        if pid == my_id:
            if at in ("raise", "allin"):
                my_pressure = True
            if r == 1 and my_first_flop and opp_cbet_this:
                my_first_flop = False
                st["ftcb_opp"] += 1
                if at == "fold":
                    st["ftcb"] += 1
            continue
        if pid != opp:
            continue
        st["total"] += 1
        if at in ("raise", "allin"):
            st["aggr"] += 1
        if at == "allin":
            st["allin"] += 1
        if r == 0 and not seen_pf:
            seen_pf = True
            st["pf_opp"] += 1
            if at in ("call", "raise", "allin"):
                st["vol"] += 1
            if at in ("raise", "allin"):
                st["pfr"] += 1
                opp_pf_raised = True
        if r > 0:
            st["post"] += 1
            if at in ("raise", "allin"):
                st["post_aggr"] += 1
            if at == "check":
                st["post_check"] += 1
        if r == 1 and opp_first_flop:
            opp_first_flop = False
            if opp_pf_raised:
                st["cbet_opp"] += 1
                if at in ("raise", "allin"):
                    st["cbet"] += 1
                    opp_cbet_this = True
        if my_pressure:
            st["ftr_opp"] += 1
            if at == "fold":
                st["ftr"] += 1
            my_pressure = False
    return st

def build_model(requests, my_id):
    opp = next_player(my_id, 1)
    hands = latest_by_hand(requests)
    keys = ["pf_opp", "vol", "pfr", "total", "aggr", "allin", "post", "post_aggr",
            "post_check", "ftr_opp", "ftr", "cbet_opp", "cbet", "ftcb_opp", "ftcb"]
    acc = {k: 0 for k in keys}
    per_vpip, per_pfr, per_pa_n, per_pa_d = [], [], [], []
    for req in hands:
        hs = track_hand(req, my_id, opp)
        for k in keys:
            acc[k] += hs[k]
        if hs["pf_opp"] > 0:
            per_vpip.append(1.0 if hs["vol"] > 0 else 0.0)
            per_pfr.append(1.0 if hs["pfr"] > 0 else 0.0)
        if hs["post"] > 0:
            per_pa_n.append(hs["post_aggr"])
            per_pa_d.append(hs["post"])
    conf = clamp((acc["total"] - 5) / 35.0, 0.0, 1.0)
    m = {
        "conf": conf, "total": acc["total"],
        "vpip": smooth(acc["vol"], acc["pf_opp"], 0.52, 4.0),
        "pfr": smooth(acc["pfr"], acc["pf_opp"], 0.24, 4.0),
        "allin_rate": smooth(acc["allin"], acc["total"], 0.05, 8.0),
        "post_aggr": smooth(acc["post_aggr"], acc["post"], 0.36, 5.0),
        "post_check": smooth(acc["post_check"], acc["post"], 0.42, 5.0),
        "ftr": smooth(acc["ftr"], acc["ftr_opp"], 0.44, 4.0),
        "aggression": smooth(acc["aggr"], acc["total"], 0.30, 6.0),
        "cbet": smooth(acc["cbet"], acc["cbet_opp"], 0.55, 4.0),
        "ftcb": smooth(acc["ftcb"], acc["ftcb_opp"], 0.40, 3.0),
        "drift": False,
    }
    if len(per_vpip) >= 12:
        n = min(10, len(per_vpip))
        all_v = sum(per_vpip) / len(per_vpip)
        rec_v = sum(per_vpip[-n:]) / n
        all_p = sum(per_pfr) / len(per_pfr)
        rec_p = sum(per_pfr[-n:]) / n
        if abs(rec_v - all_v) > 0.15 or abs(rec_p - all_p) > 0.12:
            m["drift"] = True
            m["conf"] = max(0.25, conf * 0.6)
            m["vpip"] = clamp(rec_v, 0.1, 0.95)
            m["pfr"] = clamp(rec_p, 0.0, 0.8)
            rn = sum(per_pa_n[-n:]) if per_pa_n else 0
            rd = sum(per_pa_d[-n:]) if per_pa_d else 0
            if rd > 0:
                m["post_aggr"] = clamp(rn / rd, 0.1, 0.8)
    m["preset"] = classify(m)
    return m

def classify(m):
    if m["total"] < 8:
        return "BALANCED"
    a, agg, ftr = m["allin_rate"], m["aggression"], m["ftr"]
    if a >= 0.16 or agg >= 0.52 or m["post_aggr"] >= 0.55:
        return "AGGRO"
    if ftr <= 0.30 and agg <= 0.32:
        return "VALUE"
    if ftr >= 0.62 and agg <= 0.40:
        return "AGGRO"
    if agg >= 0.40 and ftr <= 0.45:
        return "TIGHT"
    return "BALANCED"

# ═══════════════ 局面分析（★位置：SB/dealer 有位置）═══════════════
def analyze_spot(req, state):
    my_id = req["my_id"]
    opp = next_player(my_id, 1)
    dealer = req["dealer_id"]
    hist = req["history"]
    is_sb = my_id == dealer            # ★SB=庄家，翻前先动、翻后后动
    info = {"has_position": is_sb,     # ★翻后最后行动=有位置
            "is_sb": is_sb, "is_bb": not is_sb,
            "opp_pf_raises": 0, "opp_round_raises": 0, "opp_post_bets": 0,
            "opp_cur_bets": 0, "opp_post_checks": 0,
            "facing_raise": False, "facing_allin": state["opp_allin"],
            "facing_post": False, "last_type": None, "last_bb": 0.0, "last_ratio": 0.0,
            "preflop_spot": "other"}
    for rec in hist:
        if rec["player_id"] == opp and rec["round"] > 0 and rec["action_type"] == "check":
            info["opp_post_checks"] += 1
        if rec["player_id"] != opp or rec["action_type"] not in ("raise", "allin"):
            continue
        if rec["round"] == 0:
            info["opp_pf_raises"] += 1
        else:
            info["opp_post_bets"] += 1
        if rec["round"] == state["round"]:
            info["opp_round_raises"] += 1
            if rec["round"] > 0:
                info["opp_cur_bets"] += 1
    if hist and hist[-1]["player_id"] == opp:
        last = hist[-1]
        info["last_type"] = last["action_type"]
        if last["action_type"] in ("raise", "allin"):
            info["facing_raise"] = True
            info["facing_post"] = state["round"] > 0
            amt = last["action"] if last["action_type"] == "raise" else state["allin_call"]
            info["last_bb"] = amt / BIG_BLIND
            info["last_ratio"] = amt / max(1, state["pot"])
    if state["round"] == 0:
        if not hist and is_sb:
            info["preflop_spot"] = "sb_open"
        elif hist and (not is_sb) and hist[-1]["player_id"] == opp:
            if hist[-1]["action_type"] == "call":
                info["preflop_spot"] = "bb_vs_limp"
            elif hist[-1]["action_type"] in ("raise", "allin"):
                info["preflop_spot"] = "bb_vs_raise"
        elif hist and is_sb and hist[-1]["player_id"] == opp \
                and hist[-1]["action_type"] in ("raise", "allin"):
            info["preflop_spot"] = "sb_vs_reraise"
    return info

# ═══════════════ 加权范围胜率 ═══════════════
def combo_weight(combo, public, state, model, spot):
    pf = max(0.05, preflop_strength(list(combo)))
    conf = model["conf"]
    w = 0.15 + pf
    if spot["opp_pf_raises"] > 0:
        pr = 0.95 + 0.35 * spot["opp_pf_raises"] + 0.20 * spot["last_bb"]
        pr += conf * max(0.0, 0.42 - model["pfr"]) * 1.8
        pr -= conf * max(0.0, model["pfr"] - 0.38) * 0.9
        pr -= conf * model["allin_rate"] * 0.8
        w *= pf ** clamp(pr, 0.70, 2.80)
    else:
        w *= pf ** clamp(0.80 - conf * max(0.0, model["vpip"] - 0.55) * 0.5, 0.55, 1.10)
    if len(public) >= 3:
        made = made_metric(list(combo), public)
        dr = draw_profile(list(combo), public)["quality"]
        metric = max(made, 0.16 + dr)
        if spot["facing_post"] or (spot["facing_allin"] and state["round"] > 0):
            pr = 0.95 + 0.25 * spot["opp_round_raises"] + 0.35 * spot["last_ratio"]
            pr += conf * max(0.0, 0.34 - model["post_aggr"]) * 1.6
            pr -= conf * max(0.0, model["post_aggr"] - 0.46) * 0.8
            w *= max(0.08, metric) ** clamp(pr, 0.75, 2.80)
        else:
            w *= 0.40 + metric
    if spot["facing_allin"] and state["round"] == 0:
        jp = 0.90 + conf * max(0.0, 0.06 - model["allin_rate"]) * 4.0
        w *= pf ** clamp(jp, 0.90, 2.80)
    return max(w, 1e-6)

def weighted_equity(my_cards, public, state, model, spot, iters):
    used = set(my_cards + public)
    deck = [c for c in range(52) if c not in used]
    combos, weights = [], []
    for a, b in itertools.combinations(deck, 2):
        combos.append((a, b))
        weights.append(combo_weight((a, b), public, state, model, spot))
    if len(public) == 5:
        my = evaluate_best(my_cards + public)
        win = tot = 0.0
        for combo, wt in zip(combos, weights):
            op = evaluate_best(list(combo) + public)
            tot += wt
            if my > op:
                win += wt
            elif my == op:
                win += 0.5 * wt
        return 0.5 if tot <= 0 else win / tot
    cum, total = [], 0.0
    for wt in weights:
        total += wt
        cum.append(total)
    if total <= 0:
        return 0.5
    need = 5 - len(public)
    win = 0.0
    for _ in range(iters):
        combo = combos[bisect.bisect_left(cum, random.random() * total)]
        pool = [c for c in deck if c not in combo]
        board = public + random.sample(pool, need)
        my = evaluate_best(my_cards + board)
        op = evaluate_best(list(combo) + board)
        if my > op:
            win += 1
        elif my == op:
            win += 0.5
    return win / iters

def realized_equity(wr, made, draw, ridx, has_pos, spot, pp, pot):
    if ridx == 0:
        return wr
    air = made < 0.18 and draw < 0.08
    dbl = spot["opp_post_bets"] >= 2
    big = pot > 3000
    if air:
        eqr = 0.68 if has_pos else 0.56
        if dbl:
            eqr -= 0.10 + (0.05 if not has_pos else 0)
        if ridx == 2:
            eqr -= 0.05
        elif ridx == 3:
            eqr -= 0.12
        if big:
            eqr -= 0.03
        return wr * clamp(eqr, 0.40, 0.85)
    if draw >= 0.08 and made < 0.18 and not has_pos:
        eqr = 0.85 if ridx == 1 else 0.75
        if dbl:
            eqr -= 0.05
        return wr * clamp(eqr, 0.60, 0.92)
    if pp["made_class"] == 1:
        pt = pp["pair_type"]
        if pt in ("middle_pair", "bottom_pair", "underpair", "board_pair"):
            eqr = 0.84 if has_pos else 0.73
            if pp["weak_kicker"]:
                eqr -= 0.05
            if dbl:
                eqr -= 0.06 + (0.05 if not has_pos else 0)
            if ridx == 3:
                eqr -= 0.06
            if big:
                eqr -= 0.03
            return wr * clamp(eqr, 0.60, 0.92)
        if pt == "top_pair" and pp["weak_kicker"]:
            eqr = 0.92 if has_pos else 0.86
            if dbl:
                eqr -= 0.04
            return wr * clamp(eqr, 0.75, 0.95)
    return wr

def gift_balance(requests, my_id):
    opp = next_player(my_id, 1)
    g = 0.0
    for req in latest_by_hand(requests):
        tw = req.get("total_win_chips", [0, 0])
        if len(tw) <= opp:
            continue
        if tw[opp] < -200:
            g += (-tw[opp] - 200) / INITIAL_CHIPS
    return g

def exploit_lambda(g, conf):
    if conf < 0.25:
        return 0.0
    return clamp(conf * min(1.0, max(0.0, g) / 2.0), 0.0, 0.85)

# ═══════════════ 下注尺寸 ═══════════════
def build_raise(state, my_chips, wr, ridx, has_pos, model, P, tier, sbonus, wet,
                spot_name=None, pf=None, semi=False, bluff=False, probe=False,
                induce=False, nrisk=0.0):
    min_raise, to_call, pot = state["round_raise"], state["to_call"], state["pot"]
    if my_chips <= max(min_raise, to_call) + 1:
        return None
    pot_after = pot + to_call
    conf, ftr = model["conf"], model["ftr"]
    ratio = [0.55 if to_call == 0 else 0.75, 0.60, 0.70, 0.85][ridx]
    ratio += max(0.0, wr - 0.55) * (0.90 + 0.20 * ridx)
    ratio += -0.05 if has_pos else 0.05
    ratio += conf * max(0.0, ftr - 0.52) * (0.20 if semi else 0.10)
    ratio += sbonus + P["size"]
    if tier == "nut":
        ratio += 0.05 * wet
    elif tier == "thin":
        ratio -= 0.04 * wet
    if semi:
        ratio -= 0.08 + (-0.02 * wet)
    if bluff:
        ratio = min(ratio, 0.54 + 0.18 * wet)
        ratio += conf * max(0.0, ftr - 0.58) * 0.22
    if nrisk > 0.0 and tier != "nut":
        ratio -= min(0.10, nrisk * 0.55)
    if induce and to_call == 0 and tier == "nut":
        ratio = min(ratio, 0.29 + 0.05 * ridx + 0.05 * wet)
    if probe:
        pr = 0.25 + 0.08 * wet
        if tier == "thin":
            pr += 0.08
        ratio = min(ratio, pr)
    low = 0.22 if (probe or (bluff and to_call == 0)) else 0.40
    ratio = clamp(ratio, low, 1.45)
    amount = int(to_call + pot_after * ratio)
    if ridx == 0 and pf is not None:
        if spot_name == "sb_open":
            amount = max(amount, int((2.5 + max(0.0, pf - 0.58) * 1.8) * BIG_BLIND) - state["my_round_bet"])
        elif spot_name == "bb_vs_limp":
            amount = max(amount, int((3.2 + max(0.0, pf - 0.60) * 1.8) * BIG_BLIND) - state["my_round_bet"])
    amount = max(min_raise, min(amount, my_chips - 1))
    if amount <= to_call or amount < min_raise or amount >= my_chips:
        return None
    return amount

def anti_lock_attack(state, my_chips, ridx, wr, model, rh, pf, tier, draw, tex):
    if state["opp_allin"] or my_chips <= 1:
        return None
    to_call, pot = state["to_call"], state["pot"]
    if to_call >= my_chips:
        return -2
    hands_left = rh if rh is not None else TOTAL_HANDS
    weak = tier in ("none", "thin") and (draw["quality"] if draw else 0) < 0.14 and wr < 0.45
    high_fold = model["conf"] < 0.20 or model["ftr"] >= 0.42
    emergency = (hands_left <= 3 or (to_call / max(1, pot) >= 0.35)
                 or (weak and high_fold and hands_left <= 6)
                 or (wr < 0.18 and hands_left <= 5))
    if tier in ("strong", "nut") or (draw and draw["semi"]):
        emergency = emergency and hands_left <= 3
    if emergency:
        return -2
    pot_after = pot + to_call
    if ridx == 0:
        target = int(to_call + pot_after * (2.2 if to_call == 0 else 2.6))
        s = pf if pf is not None else wr
        target = max(target, int((5.5 + max(0.0, s - 0.5) * 3.0) * BIG_BLIND) - state["my_round_bet"])
    else:
        target = int(to_call + pot_after * [0, 1.15, 1.35, 1.55][ridx])
    if tex and tex["dynamic"]:
        target = int(target * 1.08)
    if weak:
        target = int(target * 1.12)
    amount = max(state["round_raise"], target)
    if amount >= my_chips * 0.72:
        return -2
    amount = min(amount, my_chips - 1)
    if amount <= to_call or amount < state["round_raise"]:
        return -2 if hands_left <= 4 else None
    return amount

def anti_lock_continue(active, wr, odds, ridx, tier, draw, made):
    if not active:
        return False
    disc = 0.07 + 0.025 * max(0, ridx)
    if tier == "nut":
        disc += 0.12
    elif tier == "strong":
        disc += 0.08
    elif tier == "thin":
        disc += 0.035
    if draw and draw["type"] in ("combo", "nut_flush"):
        disc += 0.05
    elif draw and draw["semi"]:
        disc += 0.03
    if made < 0.18 and (draw is None or draw["quality"] < 0.08):
        disc -= 0.04
    return wr >= max(0.08, odds - disc)

# ═══════════════ 翻前专用 ═══════════════
def preflop_decision(req, state, spot, model, P, pf, wr, has_pos):
    my_chips = req["my_chips"]
    to_call = state["to_call"]
    conf = model["conf"]
    loose = conf * max(0.0, model["vpip"] - 0.55) * 0.03
    trash = is_trash(req["my_cards"], pf)
    sp = spot["preflop_spot"]

    if sp == "sb_open":
        open_thr = 0.49 + 0.02 - P["widen"]
        ra = build_raise(state, my_chips, max(wr, pf), 0, has_pos, model, P, "strong", 0.0, 0.0,
                         spot_name="sb_open", pf=pf)
        if not trash and pf >= open_thr and ra is not None:
            return ra
        if pf <= 0.36 - loose:
            return -1
        return 0

    if sp == "bb_vs_limp":
        iso = 0.57 - loose - P["widen"] - conf * max(0.0, model["ftr"] - 0.52) * 0.05
        ra = build_raise(state, my_chips, max(wr, pf), 0, has_pos, model, P, "strong", 0.0, 0.0,
                         spot_name="bb_vs_limp", pf=pf)
        if not trash and pf >= iso and ra is not None:
            return ra
        return 0

    if sp == "bb_vs_raise":
        ftr = model["ftr"]
        if pf >= 0.72:
            pa = state["pot"] + to_call
            tgt = max(state["round_raise"], int(to_call + pa * (3.0 + clamp(ftr - 0.44, -0.5, 0.5)) * 0.33))
            tgt = min(tgt, my_chips - 1)
            if to_call < tgt < my_chips:
                return tgt
            return 0
        if 0.38 <= pf <= 0.52 and conf >= P["gate"] and ftr > P["bluff_ff"] - 0.07:
            hi = hand_index(req) or 0
            tok = (sum(req["my_cards"]) * 13 + hi * 7) % 100
            freq = clamp((ftr - 0.45) * 1.2, 0.0, 0.6)
            if tok < int(freq * 100):
                tgt = max(state["round_raise"], int(to_call + (state["pot"] + to_call) * 0.60))
                tgt = min(tgt, my_chips - 1)
                if to_call < tgt < my_chips:
                    return tgt
        ct = 0.42 - loose - conf * max(0.0, ftr - 0.50) * 0.04
        if pf >= ct:
            return 0
        if pf < 0.35 and to_call > BIG_BLIND * 3:
            return -1
        return 0

    if sp == "sb_vs_reraise":
        if pf >= 0.85:
            pa = state["pot"] + to_call
            tgt = max(state["round_raise"], int(to_call + pa * 0.70))
            if tgt >= my_chips * 0.5:
                return -2
            tgt = min(tgt, my_chips - 1)
            if to_call < tgt:
                return tgt
            return -2
        if pf >= 0.60 and to_call <= my_chips * 0.15:
            return 0
        return -1
    return None

# ═══════════════ 主决策 ═══════════════
def decide(req, requests):
    my_id = req["my_id"]
    my_chips = req["my_chips"]
    my_cards = req["my_cards"]
    public = req["public_cards"]

    state = reconstruct(req)
    if should_lock(req, state, my_id):
        return -1 if (state["to_call"] > 0 or state["opp_allin"]) else 0

    model = build_model(requests, my_id)
    P = PRESETS[model["preset"]]
    spot = analyze_spot(req, state)
    ridx = state["round"]
    to_call = state["to_call"]
    pot = max(1, state["pot"])
    rh = remaining_hands(req)
    anti_lock = fold_gives_opp_lock(req, state, my_id)
    lam = exploit_lambda(gift_balance(requests, my_id), model["conf"])
    pf = preflop_strength(my_cards) if ridx == 0 else None
    has_pos = spot["has_position"]

    iters = SIMS.get(len(public), 640)
    wr = weighted_equity(my_cards, public, state, model, spot, iters)
    critical = to_call > 0 and (to_call / pot >= 0.25 or to_call >= BIG_BLIND * 4 or state["opp_allin"])
    ex = EXTRA_SIMS.get(len(public), 0)
    if critical and ex > 0:
        wr = (wr * iters + weighted_equity(my_cards, public, state, model, spot, ex) * ex) / (iters + ex)

    if ridx == 0:
        act = preflop_decision(req, state, spot, model, P, pf, wr, has_pos)
        if act is not None:
            if anti_lock and act <= 0 and not is_trash(my_cards, pf):
                atk = anti_lock_attack(state, my_chips, 0, wr, model, rh, pf, "none", None, None)
                if atk is not None:
                    return atk
                if act == -1 and to_call < my_chips:
                    return 0
            return act

    made = made_metric(my_cards, public) if ridx > 0 else 0.0
    tex = board_texture(public) if ridx > 0 else {"wet": 0.0, "dynamic": False, "paired": False, "flush_p": 0.0}
    pp = pair_profile(my_cards, public) if ridx > 0 else {"made_class": -1, "pair_type": "none", "weak_kicker": False}
    draw = draw_profile(my_cards, public) if ridx > 0 else {"quality": 0.0, "semi": False, "type": "none", "ftd": 0.0}
    ds = draw["quality"]
    vt = value_tier(my_cards, public, pp, tex) if ridx > 0 else {"tier": "none", "sbonus": 0.0}
    tier = vt["tier"]
    nrisk = nutted_risk(my_cards, public, tex) if ridx > 0 else 0.0
    cls = evaluate_best(my_cards + public)[0] if ridx > 0 else 0

    strong = [0.69, 0.65, 0.61, 0.59][ridx]
    medium = [0.54, 0.50, 0.48, 0.48][ridx]
    gto_s, gto_m = strong, medium
    pos_s = -0.015 if has_pos else 0.02
    pos_m = -0.01 if has_pos else 0.015
    strong += pos_s + P["thr"]
    medium += pos_m + P["thr"]
    gto_s += pos_s
    gto_m += pos_m
    if pf is not None:
        if pf >= 0.72:
            strong -= 0.03
            medium -= 0.02
        elif pf <= 0.40:
            strong += 0.04
            medium += 0.03
    if tier == "nut":
        strong -= 0.07
        medium -= 0.04
    elif tier == "strong":
        strong -= 0.04
        medium -= 0.02
    strong += 0.45 * nrisk
    medium += 0.30 * nrisk
    strong = (1 - lam) * gto_s + lam * strong
    medium = (1 - lam) * gto_m + lam * medium

    if state["opp_allin"]:
        cost = max(state["allin_call"], to_call)
        odds = cost / (pot + cost) if cost > 0 else 0.0
        buf = 0.02 + max(0.0, strong - 0.65) * 0.2 + nrisk + (0.04 if tier == "thin" else 0)
        if anti_lock:
            buf -= 0.10
        cont = anti_lock_continue(anti_lock, wr, odds, ridx, tier, draw, made)
        buf = clamp(buf, -0.05 if anti_lock else 0.0, 0.14)
        if cls >= 2 and odds <= 0.70:
            return -2
        return -2 if (wr >= odds + buf or cont) else -1

    if to_call >= my_chips:
        odds = my_chips / (pot + my_chips)
        buf = 0.01 + max(0.0, strong - 0.64) * 0.2 + nrisk + (0.04 if tier == "thin" else 0)
        if anti_lock:
            buf -= 0.10
        cont = anti_lock_continue(anti_lock, wr, odds, ridx, tier, draw, made)
        buf = clamp(buf, -0.05 if anti_lock else 0.0, 0.14)
        if cls >= 2 and odds <= 0.70:
            return -2
        return -2 if (wr >= odds + buf or cont) else -1

    if to_call > 0:
        odds = to_call / (pot + to_call)
        rr = realized_equity(wr, made, ds, ridx, has_pos, spot, pp, pot)
        margin = 0.0
        if ridx > 0:
            bet_frac = to_call / pot
            margin -= P["thr"] * 0.5
            if draw["semi"]:
                margin -= 0.04
            margin += 0.50 * nrisk
            if ridx == 1 and spot["facing_post"]:
                if model["cbet"] > 0.65:
                    margin -= 0.02
                elif model["cbet"] < 0.40:
                    margin += 0.02
            if bet_frac <= 0.55:
                mdf = 0.55 + (0.13 if model["preset"] == "AGGRO" else 0)
                mdf_eq = max(odds - 0.05, (1 - mdf) * odds)
                if rr >= mdf_eq:
                    margin = min(margin, rr - odds - 0.001)
        if anti_lock:
            margin -= 0.07
        cont = anti_lock_continue(anti_lock, wr, odds, ridx, tier, draw, made)
        if anti_lock and (ridx > 0 or is_3bet_candidate(my_cards)):
            atk = anti_lock_attack(state, my_chips, ridx, wr, model, rh, pf, tier, draw, tex)
            if atk is not None:
                return atk
        if rr < odds + margin and not cont:
            if draw["semi"] and odds < 0.35:
                return 0
            return -1
        if wr >= max(strong, odds + 0.12):
            ra = build_raise(state, my_chips, wr, ridx, has_pos, model, P, tier, vt["sbonus"], tex["wet"], nrisk=nrisk)
            if ra is not None:
                return ra
        if ridx > 0 and draw["semi"] and ds >= 0.12 and model["conf"] >= P["gate"] and model["ftr"] > P["bluff_ff"]:
            ra = build_raise(state, my_chips, wr, ridx, has_pos, model, P, tier, vt["sbonus"], tex["wet"], semi=True)
            if ra is not None:
                return ra
        return 0

    if anti_lock:
        atk = anti_lock_attack(state, my_chips, ridx, wr, model, rh, pf, tier, draw, tex)
        if atk is not None:
            return atk

    can_bet = wr >= medium or tier in ("strong", "nut") or made >= 0.62
    semi = (ridx > 0 and draw["semi"] and ds >= 0.12 and
            model["conf"] >= P["gate"] and model["ftr"] > P["bluff_ff"])
    induce = (ridx > 0 and tier == "nut" and not tex["dynamic"] and pot < 1600
              and model["conf"] >= 0.20 and model["post_aggr"] >= 0.38)
    bluff = (ridx > 0 and made < 0.18 and ds < 0.08 and
             model["conf"] >= P["gate"] + 0.05 and model["ftr"] > P["bluff_ff"] + 0.05 and
             random.random() < (0.35 if model["preset"] == "AGGRO" else 0.12))
    if can_bet or semi or bluff:
        ra = build_raise(state, my_chips, wr, ridx, has_pos, model, P, tier, vt["sbonus"], tex["wet"],
                         semi=semi and not can_bet, bluff=bluff and not can_bet and not semi,
                         induce=induce, nrisk=nrisk)
        if ra is not None:
            return ra
    return 0

# ═══════════════ 合法化 ═══════════════
def sanitize(action, state, my_chips):
    try:
        if state["opp_allin"]:
            return action if action in (-1, -2) else -1
        if state["to_call"] >= my_chips:
            return -2 if action == -2 else -1
        if action == -2:
            return -2 if my_chips > 0 else 0
        if action == -1:
            return -1
        if action == 0:
            return 0
        if action > 0:
            if action >= my_chips:
                return -2
            if action < state["round_raise"] or action <= state["to_call"]:
                return 0 if state["to_call"] == 0 else -1
            return int(action)
        return 0
    except Exception:
        return 0

def safe_decide(requests):
    """永不抛异常，永远返回合法动作码"""
    if not requests:
        return -1
    req = requests[-1]
    try:
        state = reconstruct(req)
    except Exception:
        return 0
    try:
        random.seed((hand_index(req) or 0) * 100003 + len(req.get("history", [])) * 131 + int(req.get("my_id", 0)))
        action = decide(req, requests)
    except Exception:
        action = 0 if (state["to_call"] == 0 and not state["opp_allin"]) else -1
    return sanitize(action, state, req["my_chips"])

# ═══════════════ 通信主循环（Traditional + LongRunning 双兼容）═══════════════
def main():
    accumulated = []          # 累积所有历史 request（LongRunning 用内存维护）
    first = True
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            env = json.loads(line)
        except Exception:
            print(json.dumps({"response": -1}), flush=True)
            continue
        if isinstance(env, dict) and "requests" in env:
            reqs = env.get("requests") or []
            accumulated = list(reqs)          # Traditional：每次给全量历史
        elif isinstance(env, dict) and "request" in env:
            accumulated.append(env["request"])  # LongRunning：增量追加
        elif isinstance(env, dict):
            accumulated.append(env)
        else:
            print(json.dumps({"response": -1}), flush=True)
            continue

        action = safe_decide(accumulated)
        print(json.dumps({"response": int(action)}, separators=(",", ":")), flush=True)

        if first:
            print(KEEP_RUNNING, flush=True)   # 首响应后输出握手，兼容两种模式
            first = False

if __name__ == "__main__":
    main()
