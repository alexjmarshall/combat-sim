"""
Sequential game strategy: defender commits dice and announces maneuver, then attacker responds.

Key difference from strategy.py: the attacker's maneuver is a deterministic best-response to the
observed defense (threshold-based), not a probabilistic blind choice. The attacker's commit level
is still chosen blind, before the defense is announced.
"""

import math
import random
from dataclasses import dataclass
from combat_seq import Maneuver, CombatantState, resolve_exchange

REFRESH_START_OF_TURN = True
REFRESH_END_OF_TURN = False
COMBATANT_DICE = 10
INITIATIVE_LOSER_PENALTY = 0.5


def _int_commit(fraction, reserve, min_val=1):
    if reserve <= 0:
        return 0
    return max(min_val, min(reserve, int(round(reserve * fraction))))


def choose_defense(strat, defender, atk_commit):
    if defender.reserve <= 0:
        return Maneuver.DEFENSELESS, 0
    commit_ratio = atk_commit / max(1, defender.reserve)
    is_low = commit_ratio < strat.commit_ratio_threshold
    if is_low:
        if random.random() < strat.dodge_prob_vs_low:
            return Maneuver.DODGE, _int_commit(strat.dodge_commit_vs_low_frac, defender.reserve)
        if random.random() < strat.counter_prob_vs_low:
            return Maneuver.COUNTER, _int_commit(strat.counter_commit_vs_low_frac, defender.reserve)
        return Maneuver.PARRY, _int_commit(strat.parry_commit_vs_low_frac, defender.reserve)
    else:
        if random.random() < strat.dodge_prob_vs_high:
            return Maneuver.DODGE, _int_commit(strat.dodge_commit_vs_high_frac, defender.reserve)
        if random.random() < strat.counter_prob_vs_high:
            return Maneuver.COUNTER, _int_commit(strat.counter_commit_vs_high_frac, defender.reserve)
        return Maneuver.PARRY, _int_commit(strat.parry_commit_vs_high_frac, defender.reserve)


def choose_dodge_roll(strat, reserve_after_commit, side, opp_maneuver, is_low_threat=False):
    if reserve_after_commit <= 0:
        return 0
    if opp_maneuver in (Maneuver.DODGE, Maneuver.PARRY):
        return 0
    if side == 'atk':
        frac = strat.dodge_roll_atk_frac
    else:
        frac = strat.dodge_roll_vs_low_frac if is_low_threat else strat.dodge_roll_vs_high_frac
    return max(0, min(reserve_after_commit, int(round(reserve_after_commit * frac))))


def decide_continue(strat, result, attacker):
    if attacker.reserve <= max(1, int(attacker.max_hd * strat.min_reserve_frac_to_continue)):
        return False
    if result.defender_damage_taken > 0:
        return random.random() < strat.continue_after_hit_dealt_prob
    return random.random() < strat.continue_after_whiff_prob



@dataclass
class SequentialStrategy:
    # Attacker — commit (blind, chosen before defense is announced)
    attack_commit_frac: float = 0.5

    # Attacker — maneuver response thresholds (chosen after observing defense)
    # vs Parry: Feint when atk_commit / def_commit < threshold, else SA
    feint_parry_threshold: float = 1.0
    feint_followup_vs_parry_frac: float = 0.6
    # vs Counter: Dodge when def_commit / atk_commit > threshold, else SA (accept the hit)
    dodge_counter_threshold: float = 0.8
    dodge_roll_frac: float = 0.4
    # vs Dodge: always SA (no threshold — SA is dominantly correct)

    # Attacker — continuation
    continue_after_hit_dealt_prob: float = 0.5
    continue_after_whiff_prob: float = 0.8
    min_reserve_frac_to_continue: float = 0.15

    # Defender (same role as in Strategy; acts without knowing attacker's maneuver)
    commit_ratio_threshold: float = 0.5
    counter_prob_vs_low: float = 0.4
    parry_commit_vs_low_frac: float = 0.3
    counter_commit_vs_low_frac: float = 0.4
    counter_prob_vs_high: float = 0.3
    parry_commit_vs_high_frac: float = 0.7
    counter_commit_vs_high_frac: float = 0.5
    dodge_prob_vs_low: float = 0.05
    dodge_commit_vs_low_frac: float = 0.1
    dodge_roll_vs_low_frac: float = 0.3
    dodge_prob_vs_high: float = 0.05
    dodge_commit_vs_high_frac: float = 0.1
    dodge_roll_vs_high_frac: float = 0.5

    def clip(self):
        def c(x, lo=0.01, hi=0.99):
            return max(lo, min(hi, x))
        return SequentialStrategy(
            attack_commit_frac=c(self.attack_commit_frac, 0.1, 0.99),
            feint_parry_threshold=c(self.feint_parry_threshold, 0.2, 3.0),
            feint_followup_vs_parry_frac=c(self.feint_followup_vs_parry_frac),
            dodge_counter_threshold=c(self.dodge_counter_threshold, 0.2, 3.0),
            dodge_roll_frac=c(self.dodge_roll_frac),
            continue_after_hit_dealt_prob=c(self.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=c(self.continue_after_whiff_prob),
            min_reserve_frac_to_continue=c(self.min_reserve_frac_to_continue, 0.05, 0.6),
            commit_ratio_threshold=c(self.commit_ratio_threshold),
            counter_prob_vs_low=c(self.counter_prob_vs_low),
            parry_commit_vs_low_frac=c(self.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=c(self.counter_commit_vs_low_frac),
            counter_prob_vs_high=c(self.counter_prob_vs_high),
            parry_commit_vs_high_frac=c(self.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=c(self.counter_commit_vs_high_frac),
            dodge_prob_vs_low=c(self.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=c(self.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=c(self.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=c(self.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=c(self.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=c(self.dodge_roll_vs_high_frac),
        )

    def mutate(self, rate=0.08):
        def m(x):
            return x + random.gauss(0, rate)
        return SequentialStrategy(
            attack_commit_frac=m(self.attack_commit_frac),
            feint_parry_threshold=m(self.feint_parry_threshold),
            feint_followup_vs_parry_frac=m(self.feint_followup_vs_parry_frac),
            dodge_counter_threshold=m(self.dodge_counter_threshold),
            dodge_roll_frac=m(self.dodge_roll_frac),
            continue_after_hit_dealt_prob=m(self.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=m(self.continue_after_whiff_prob),
            min_reserve_frac_to_continue=m(self.min_reserve_frac_to_continue),
            commit_ratio_threshold=m(self.commit_ratio_threshold),
            counter_prob_vs_low=m(self.counter_prob_vs_low),
            parry_commit_vs_low_frac=m(self.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=m(self.counter_commit_vs_low_frac),
            counter_prob_vs_high=m(self.counter_prob_vs_high),
            parry_commit_vs_high_frac=m(self.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=m(self.counter_commit_vs_high_frac),
            dodge_prob_vs_low=m(self.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=m(self.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=m(self.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=m(self.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=m(self.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=m(self.dodge_roll_vs_high_frac),
        ).clip()

    @staticmethod
    def random():
        return SequentialStrategy(
            attack_commit_frac=random.uniform(0.2, 0.99),
            feint_parry_threshold=random.uniform(0.2, 3.0),
            feint_followup_vs_parry_frac=random.random(),
            dodge_counter_threshold=random.uniform(0.2, 3.0),
            dodge_roll_frac=random.random(),
            continue_after_hit_dealt_prob=random.random(),
            continue_after_whiff_prob=random.random(),
            min_reserve_frac_to_continue=random.uniform(0.05, 0.4),
            commit_ratio_threshold=random.uniform(0.3, 0.7),
            counter_prob_vs_low=random.random(),
            parry_commit_vs_low_frac=random.random(),
            counter_commit_vs_low_frac=random.random(),
            counter_prob_vs_high=random.random(),
            parry_commit_vs_high_frac=random.random(),
            counter_commit_vs_high_frac=random.random(),
            dodge_prob_vs_low=random.random(),
            dodge_commit_vs_low_frac=random.uniform(0.05, 0.6),
            dodge_roll_vs_low_frac=random.random(),
            dodge_prob_vs_high=random.random(),
            dodge_commit_vs_high_frac=random.uniform(0.05, 0.6),
            dodge_roll_vs_high_frac=random.random(),
        ).clip()

    @staticmethod
    def crossover(a, b):
        def pick(va, vb):
            return va if random.random() < 0.5 else vb
        return SequentialStrategy(
            attack_commit_frac=pick(a.attack_commit_frac, b.attack_commit_frac),
            feint_parry_threshold=pick(a.feint_parry_threshold, b.feint_parry_threshold),
            feint_followup_vs_parry_frac=pick(a.feint_followup_vs_parry_frac, b.feint_followup_vs_parry_frac),
            dodge_counter_threshold=pick(a.dodge_counter_threshold, b.dodge_counter_threshold),
            dodge_roll_frac=pick(a.dodge_roll_frac, b.dodge_roll_frac),
            continue_after_hit_dealt_prob=pick(a.continue_after_hit_dealt_prob, b.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=pick(a.continue_after_whiff_prob, b.continue_after_whiff_prob),
            min_reserve_frac_to_continue=pick(a.min_reserve_frac_to_continue, b.min_reserve_frac_to_continue),
            commit_ratio_threshold=pick(a.commit_ratio_threshold, b.commit_ratio_threshold),
            counter_prob_vs_low=pick(a.counter_prob_vs_low, b.counter_prob_vs_low),
            parry_commit_vs_low_frac=pick(a.parry_commit_vs_low_frac, b.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=pick(a.counter_commit_vs_low_frac, b.counter_commit_vs_low_frac),
            counter_prob_vs_high=pick(a.counter_prob_vs_high, b.counter_prob_vs_high),
            parry_commit_vs_high_frac=pick(a.parry_commit_vs_high_frac, b.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=pick(a.counter_commit_vs_high_frac, b.counter_commit_vs_high_frac),
            dodge_prob_vs_low=pick(a.dodge_prob_vs_low, b.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=pick(a.dodge_commit_vs_low_frac, b.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=pick(a.dodge_roll_vs_low_frac, b.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=pick(a.dodge_prob_vs_high, b.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=pick(a.dodge_commit_vs_high_frac, b.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=pick(a.dodge_roll_vs_high_frac, b.dodge_roll_vs_high_frac),
        )


def choose_attack_response(strat, ac, def_maneuver, def_commit, atk_reserve_after):
    """
    Choose attacker's maneuver after observing the defender's committed maneuver and dice count.
    Returns the best-response maneuver based on evolved threshold parameters.
    atk_reserve_after is available for future threshold logic (unused currently).
    """
    if def_maneuver == Maneuver.PARRY:
        if ac / max(1, def_commit) < strat.feint_parry_threshold:
            return Maneuver.FEINT
        return Maneuver.SIMPLE_ATTACK
    elif def_maneuver == Maneuver.COUNTER:
        if def_commit / max(1, ac) > strat.dodge_counter_threshold:
            return Maneuver.DODGE
        return Maneuver.SIMPLE_ATTACK
    # vs Dodge or Defenseless: SA is the correct dominant response
    return Maneuver.SIMPLE_ATTACK


def run_combat_sequential(strat_a, strat_b, hd_a=COMBATANT_DICE, hd_b=COMBATANT_DICE,
                          max_turns=60, track_stats=False):
    state_a = CombatantState(max_hd=hd_a, reserve=hd_a)
    state_b = CombatantState(max_hd=hd_b, reserve=hd_b)
    strats = [strat_a, strat_b]
    states = [state_a, state_b]
    initiative = random.randint(0, 1)
    attacker_idx = initiative
    loser = states[1 - initiative]
    loser.reserve = math.ceil(loser.reserve * INITIATIVE_LOSER_PENALTY)

    stats = {
        'total_exchanges': 0,
        'response_to_parry': {'Feint': 0, 'SA': 0},
        'response_to_counter': {'SA': 0, 'Dodge': 0},
        'response_to_dodge': {'SA': 0},
        'def_maneuver_dist': {'Parry': 0, 'Counter': 0, 'Dodge': 0, 'Defenseless': 0},
        'commits_atk': [],
        'commits_def': [],
        'exchanges_per_turn': [],
        'hit_damages': [],
        'bout_max_damage': 0,
        'first_blood_loser': None,
        'initiative_winner': initiative,
    }

    turns = 0
    while turns < max_turns:
        turns += 1
        atk_idx = attacker_idx
        def_idx = 1 - atk_idx
        atk_state = states[atk_idx]
        def_state = states[def_idx]
        atk_strat = strats[atk_idx]
        def_strat = strats[def_idx]

        if REFRESH_START_OF_TURN:
            atk_state.refresh()
        if REFRESH_END_OF_TURN:
            def_state.refresh()

        exchanges_this_turn = 0
        while True:
            if exchanges_this_turn > 50:
                break
            if atk_state.reserve < 1:
                break

            # Step 1: attacker commits dice (blind — maneuver not yet chosen)
            ac = _int_commit(atk_strat.attack_commit_frac, atk_state.reserve)
            if ac < 1 or ac > atk_state.reserve:
                break

            # Step 2: defender sees attacker's commit, announces maneuver and commits dice
            dm, dc = choose_defense(def_strat, def_state, ac)
            if dc > def_state.reserve:
                dc = def_state.reserve
            if dc < 0:
                dc = 0

            # Step 3: attacker sees defense, chooses maneuver as best-response
            atk_reserve_after = atk_state.reserve - ac
            def_reserve_after = def_state.reserve - dc
            am = choose_attack_response(atk_strat, ac, dm, dc, atk_reserve_after)

            # Step 4: followup commits (attacker: feint followup or dodge roll; defender: dodge roll)
            if am == Maneuver.FEINT:
                atk_fu = _int_commit(atk_strat.feint_followup_vs_parry_frac, atk_reserve_after, min_val=0)
            elif am == Maneuver.DODGE:
                atk_fu = _int_commit(atk_strat.dodge_roll_frac, atk_reserve_after, min_val=0)
            else:
                atk_fu = 0

            is_low_threat = (ac / max(1, def_state.reserve)) < def_strat.commit_ratio_threshold
            def_fu = choose_dodge_roll(def_strat, def_reserve_after, 'def', am, is_low_threat) \
                if dm == Maneuver.DODGE else 0

            if track_stats:
                stats['total_exchanges'] += 1
                if dm == Maneuver.PARRY:
                    stats['def_maneuver_dist']['Parry'] += 1
                    stats['response_to_parry']['Feint' if am == Maneuver.FEINT else 'SA'] += 1
                elif dm == Maneuver.COUNTER:
                    stats['def_maneuver_dist']['Counter'] += 1
                    stats['response_to_counter']['Dodge' if am == Maneuver.DODGE else 'SA'] += 1
                elif dm == Maneuver.DODGE:
                    stats['def_maneuver_dist']['Dodge'] += 1
                    stats['response_to_dodge']['SA'] += 1
                else:
                    stats['def_maneuver_dist']['Defenseless'] += 1
                stats['commits_atk'].append(ac)
                stats['commits_def'].append(dc)

            result = resolve_exchange(atk_state, def_state, ac, dc, am, dm,
                                      atk_followup_commit=atk_fu,
                                      def_followup_commit=def_fu)

            if track_stats:
                for dmg, loser_idx in ((result.attacker_damage_taken, atk_idx),
                                       (result.defender_damage_taken, def_idx)):
                    if dmg > 0:
                        stats['hit_damages'].append(dmg)
                        if dmg > stats['bout_max_damage']:
                            stats['bout_max_damage'] = dmg
                        if stats['first_blood_loser'] is None:
                            stats['first_blood_loser'] = loser_idx

            exchanges_this_turn += 1

            if atk_state.total_hd <= 0:
                if track_stats:
                    stats['exchanges_per_turn'].append(exchanges_this_turn)
                return (def_idx, turns, stats)
            if def_state.total_hd <= 0:
                if track_stats:
                    stats['exchanges_per_turn'].append(exchanges_this_turn)
                return (atk_idx, turns, stats)

            if not decide_continue(atk_strat, result, atk_state):
                break

        if track_stats:
            stats['exchanges_per_turn'].append(exchanges_this_turn)

        attacker_idx = 1 - attacker_idx

    if state_a.total_hd > state_b.total_hd:
        return (0, turns, stats)
    elif state_b.total_hd > state_a.total_hd:
        return (1, turns, stats)
    return (None, turns, stats)
