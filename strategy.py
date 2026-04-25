"""V4 strategy."""

import random
from dataclasses import dataclass
from combat import Maneuver, CombatantState, resolve_exchange, WEAPON_BONUS, DECEPTIVE_ATTACK as DECEPTIVE_ATTACK_ENABLED

REFRESH_START_OF_TURN = True
REFRESH_END_OF_TURN = False
COMBATANT_DICE = 5
INITIATIVE_LOSER_PENALTY = 0.5  # fraction of dice the initiative loser starts with (1.0 = no penalty)

@dataclass
class Strategy:
    # Attacker
    feint_prob: float = 0.4
    sa_commit_frac: float = 0.5
    feint_commit_frac: float = 0.2  # the nominal feint commit (now mostly signaling)
    feint_followup_vs_parry_frac: float = 0.6
    feint_followup_vs_counter_frac: float = 0.4
    continue_after_hit_dealt_prob: float = 0.5
    continue_after_whiff_prob: float = 0.8
    dodge_prob_atk: float = 0.05
    dodge_commit_atk_frac: float = 0.1
    dodge_roll_atk_frac: float = 0.4
    da_prob: float = 0.1
    da_commit_frac: float = 0.4
    da_bonus_frac: float = 0.3
    evasive_atk_frac: float = 0.3

    # Defender
    commit_ratio_threshold: float = 0.5
    counter_prob_vs_low: float = 0.5
    parry_commit_vs_low_frac: float = 0.3
    counter_commit_vs_low_frac: float = 0.4
    counter_prob_vs_high: float = 0.3
    parry_commit_vs_high_frac: float = 0.7
    counter_commit_vs_high_frac: float = 0.5
    min_reserve_frac_to_continue: float = 0.15
    dodge_prob_vs_low: float = 0.05
    dodge_commit_vs_low_frac: float = 0.1
    dodge_roll_vs_low_frac: float = 0.3
    dodge_prob_vs_high: float = 0.05
    dodge_commit_vs_high_frac: float = 0.1
    dodge_roll_vs_high_frac: float = 0.5
    evasive_vs_low_frac: float = 0.3
    evasive_vs_high_frac: float = 0.3

    def clip(self):
        def c(x, lo=0.01, hi=0.99):
            return max(lo, min(hi, x))
        return Strategy(
            feint_prob=c(self.feint_prob),
            sa_commit_frac=c(self.sa_commit_frac),
            feint_commit_frac=c(self.feint_commit_frac),
            feint_followup_vs_parry_frac=c(self.feint_followup_vs_parry_frac),
            feint_followup_vs_counter_frac=c(self.feint_followup_vs_counter_frac),
            continue_after_hit_dealt_prob=c(self.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=c(self.continue_after_whiff_prob),
            dodge_prob_atk=c(self.dodge_prob_atk),
            dodge_commit_atk_frac=c(self.dodge_commit_atk_frac),
            dodge_roll_atk_frac=c(self.dodge_roll_atk_frac),
            da_prob=c(self.da_prob),
            da_commit_frac=c(self.da_commit_frac),
            da_bonus_frac=c(self.da_bonus_frac),
            evasive_atk_frac=c(self.evasive_atk_frac),
            commit_ratio_threshold=c(self.commit_ratio_threshold),
            counter_prob_vs_low=c(self.counter_prob_vs_low),
            parry_commit_vs_low_frac=c(self.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=c(self.counter_commit_vs_low_frac),
            counter_prob_vs_high=c(self.counter_prob_vs_high),
            parry_commit_vs_high_frac=c(self.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=c(self.counter_commit_vs_high_frac),
            min_reserve_frac_to_continue=c(self.min_reserve_frac_to_continue, 0.05, 0.6),
            dodge_prob_vs_low=c(self.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=c(self.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=c(self.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=c(self.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=c(self.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=c(self.dodge_roll_vs_high_frac),
            evasive_vs_low_frac=c(self.evasive_vs_low_frac),
            evasive_vs_high_frac=c(self.evasive_vs_high_frac),
        )

    def mutate(self, rate=0.08):
        def m(x):
            return x + random.gauss(0, rate)
        return Strategy(
            feint_prob=m(self.feint_prob),
            sa_commit_frac=m(self.sa_commit_frac),
            feint_commit_frac=m(self.feint_commit_frac),
            feint_followup_vs_parry_frac=m(self.feint_followup_vs_parry_frac),
            feint_followup_vs_counter_frac=m(self.feint_followup_vs_counter_frac),
            continue_after_hit_dealt_prob=m(self.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=m(self.continue_after_whiff_prob),
            dodge_prob_atk=m(self.dodge_prob_atk),
            dodge_commit_atk_frac=m(self.dodge_commit_atk_frac),
            dodge_roll_atk_frac=m(self.dodge_roll_atk_frac),
            da_prob=m(self.da_prob),
            da_commit_frac=m(self.da_commit_frac),
            da_bonus_frac=m(self.da_bonus_frac),
            evasive_atk_frac=m(self.evasive_atk_frac),
            commit_ratio_threshold=m(self.commit_ratio_threshold),
            counter_prob_vs_low=m(self.counter_prob_vs_low),
            parry_commit_vs_low_frac=m(self.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=m(self.counter_commit_vs_low_frac),
            counter_prob_vs_high=m(self.counter_prob_vs_high),
            parry_commit_vs_high_frac=m(self.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=m(self.counter_commit_vs_high_frac),
            min_reserve_frac_to_continue=m(self.min_reserve_frac_to_continue),
            dodge_prob_vs_low=m(self.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=m(self.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=m(self.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=m(self.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=m(self.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=m(self.dodge_roll_vs_high_frac),
            evasive_vs_low_frac=m(self.evasive_vs_low_frac),
            evasive_vs_high_frac=m(self.evasive_vs_high_frac),
        ).clip()

    @staticmethod
    def random():
        return Strategy(
            feint_prob=random.random(),
            sa_commit_frac=random.uniform(0.2, 0.99),
            feint_commit_frac=random.uniform(0.05, 0.8),
            feint_followup_vs_parry_frac=random.random(),
            feint_followup_vs_counter_frac=random.random(),
            continue_after_hit_dealt_prob=random.random(),
            continue_after_whiff_prob=random.random(),
            dodge_prob_atk=random.random(),
            dodge_commit_atk_frac=random.uniform(0.05, 0.6),
            dodge_roll_atk_frac=random.random(),
            da_prob=random.random(),
            da_commit_frac=random.uniform(0.2, 0.99),
            da_bonus_frac=random.random(),
            evasive_atk_frac=random.uniform(0.05, 0.8),
            commit_ratio_threshold=random.uniform(0.3, 0.7),
            counter_prob_vs_low=random.random(),
            parry_commit_vs_low_frac=random.random(),
            counter_commit_vs_low_frac=random.random(),
            counter_prob_vs_high=random.random(),
            parry_commit_vs_high_frac=random.random(),
            counter_commit_vs_high_frac=random.random(),
            min_reserve_frac_to_continue=random.uniform(0.05, 0.4),
            dodge_prob_vs_low=random.random(),
            dodge_commit_vs_low_frac=random.uniform(0.05, 0.6),
            dodge_roll_vs_low_frac=random.random(),
            dodge_prob_vs_high=random.random(),
            dodge_commit_vs_high_frac=random.uniform(0.05, 0.6),
            dodge_roll_vs_high_frac=random.random(),
            evasive_vs_low_frac=random.uniform(0.05, 0.8),
            evasive_vs_high_frac=random.uniform(0.05, 0.8),
        ).clip()

    @staticmethod
    def crossover(a, b):
        def pick(va, vb):
            return va if random.random() < 0.5 else vb
        return Strategy(
            feint_prob=pick(a.feint_prob, b.feint_prob),
            sa_commit_frac=pick(a.sa_commit_frac, b.sa_commit_frac),
            feint_commit_frac=pick(a.feint_commit_frac, b.feint_commit_frac),
            feint_followup_vs_parry_frac=pick(a.feint_followup_vs_parry_frac, b.feint_followup_vs_parry_frac),
            feint_followup_vs_counter_frac=pick(a.feint_followup_vs_counter_frac, b.feint_followup_vs_counter_frac),
            continue_after_hit_dealt_prob=pick(a.continue_after_hit_dealt_prob, b.continue_after_hit_dealt_prob),
            continue_after_whiff_prob=pick(a.continue_after_whiff_prob, b.continue_after_whiff_prob),
            dodge_prob_atk=pick(a.dodge_prob_atk, b.dodge_prob_atk),
            dodge_commit_atk_frac=pick(a.dodge_commit_atk_frac, b.dodge_commit_atk_frac),
            dodge_roll_atk_frac=pick(a.dodge_roll_atk_frac, b.dodge_roll_atk_frac),
            da_prob=pick(a.da_prob, b.da_prob),
            da_commit_frac=pick(a.da_commit_frac, b.da_commit_frac),
            da_bonus_frac=pick(a.da_bonus_frac, b.da_bonus_frac),
            evasive_atk_frac=pick(a.evasive_atk_frac, b.evasive_atk_frac),
            commit_ratio_threshold=pick(a.commit_ratio_threshold, b.commit_ratio_threshold),
            counter_prob_vs_low=pick(a.counter_prob_vs_low, b.counter_prob_vs_low),
            parry_commit_vs_low_frac=pick(a.parry_commit_vs_low_frac, b.parry_commit_vs_low_frac),
            counter_commit_vs_low_frac=pick(a.counter_commit_vs_low_frac, b.counter_commit_vs_low_frac),
            counter_prob_vs_high=pick(a.counter_prob_vs_high, b.counter_prob_vs_high),
            parry_commit_vs_high_frac=pick(a.parry_commit_vs_high_frac, b.parry_commit_vs_high_frac),
            counter_commit_vs_high_frac=pick(a.counter_commit_vs_high_frac, b.counter_commit_vs_high_frac),
            min_reserve_frac_to_continue=pick(a.min_reserve_frac_to_continue, b.min_reserve_frac_to_continue),
            dodge_prob_vs_low=pick(a.dodge_prob_vs_low, b.dodge_prob_vs_low),
            dodge_commit_vs_low_frac=pick(a.dodge_commit_vs_low_frac, b.dodge_commit_vs_low_frac),
            dodge_roll_vs_low_frac=pick(a.dodge_roll_vs_low_frac, b.dodge_roll_vs_low_frac),
            dodge_prob_vs_high=pick(a.dodge_prob_vs_high, b.dodge_prob_vs_high),
            dodge_commit_vs_high_frac=pick(a.dodge_commit_vs_high_frac, b.dodge_commit_vs_high_frac),
            dodge_roll_vs_high_frac=pick(a.dodge_roll_vs_high_frac, b.dodge_roll_vs_high_frac),
            evasive_vs_low_frac=pick(a.evasive_vs_low_frac, b.evasive_vs_low_frac),
            evasive_vs_high_frac=pick(a.evasive_vs_high_frac, b.evasive_vs_high_frac),
        )


def _int_commit(fraction, reserve, min_val=1):
    if reserve <= 0:
        return 0
    return max(min_val, min(reserve, int(round(reserve * fraction))))


_LETTER = {
    Maneuver.SIMPLE_ATTACK: 'SA',
    Maneuver.FEINT: 'F',
    Maneuver.DODGE: 'D',
    Maneuver.PARRY: 'P',
    Maneuver.COUNTER: 'C',
    Maneuver.DECEPTIVE_ATTACK: 'DA',
    Maneuver.DEFENSELESS: 'X',
}


def _letter(m):
    return _LETTER[m]


def choose_attack(strat, attacker):
    r = random.random()
    p_dodge = strat.dodge_prob_atk
    p_feint = (1 - p_dodge) * strat.feint_prob
    p_da = (1 - p_dodge) * (1 - strat.feint_prob) * strat.da_prob if DECEPTIVE_ATTACK_ENABLED else 0
    if r < p_dodge:
        return Maneuver.DODGE, _int_commit(strat.dodge_commit_atk_frac, attacker.reserve)
    if r < p_dodge + p_feint:
        return Maneuver.FEINT, _int_commit(strat.feint_commit_frac, attacker.reserve)
    if r < p_dodge + p_feint + p_da:
        return Maneuver.DECEPTIVE_ATTACK, _int_commit(strat.da_commit_frac, attacker.reserve)
    return Maneuver.SIMPLE_ATTACK, _int_commit(strat.sa_commit_frac, attacker.reserve)


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


def choose_followup(strat, reserve_after_commit, def_maneuver):
    if def_maneuver == Maneuver.PARRY:
        frac = strat.feint_followup_vs_parry_frac
    else:
        frac = strat.feint_followup_vs_counter_frac
    return max(0, min(reserve_after_commit, int(round(reserve_after_commit * frac))))


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


def run_combat(strat_a, strat_b, hd_a=COMBATANT_DICE, hd_b=COMBATANT_DICE, max_turns=60, track_stats=False):
    state_a = CombatantState(max_hd=hd_a, reserve=hd_a)
    state_b = CombatantState(max_hd=hd_b, reserve=hd_b)
    strats = [strat_a, strat_b]
    states = [state_a, state_b]
    initiative = random.randint(0, 1)
    attacker_idx = initiative
    loser = states[1 - initiative]
    loser.reserve = int(loser.reserve * INITIATIVE_LOSER_PENALTY)
    
    stats = {
        'maneuvers': {
            'SA_vs_P': 0, 'SA_vs_C': 0, 'SA_vs_D': 0, 'SA_vs_X': 0,
            'F_vs_P': 0, 'F_vs_C': 0, 'F_vs_D': 0, 'F_vs_X': 0,
            'D_vs_P': 0, 'D_vs_C': 0, 'D_vs_D': 0, 'D_vs_X': 0,
            'DA_vs_P': 0, 'DA_vs_C': 0, 'DA_vs_D': 0, 'DA_vs_X': 0,
        },
        'total_exchanges': 0,
        'initiative_winner': initiative,
        'commits_by_maneuver': {'SA': [], 'F': [], 'P': [], 'C': [], 'D': [], 'DR': [],
                                'DA': [], 'DA_BONUS': [], 'EA': []},
        'exchanges_per_turn': [],
        'hit_damages': [],
        'bout_max_damage': 0,
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
            am, ac = choose_attack(atk_strat, atk_state)
            if ac < 1 or ac > atk_state.reserve:
                break
            dm, dc = choose_defense(def_strat, def_state, ac)
            if dc > def_state.reserve:
                dc = def_state.reserve
            # FIX: Allow attacks against undefended opponents.
            # If defender has 0 reserve, they commit 0 dice and the attack lands unopposed.
            if dc < 0:
                dc = 0

            atk_reserve_after = atk_state.reserve - ac
            def_reserve_after = def_state.reserve - dc
            is_low_threat = (ac / max(1, def_state.reserve)) < def_strat.commit_ratio_threshold

            if am == Maneuver.FEINT:
                atk_fu = choose_followup(atk_strat, atk_reserve_after, dm)
            elif am == Maneuver.DODGE:
                atk_fu = choose_dodge_roll(atk_strat, atk_reserve_after, 'atk', dm)
            else:
                atk_fu = 0

            if am == Maneuver.DECEPTIVE_ATTACK:
                atk_bonus = max(0, min(atk_reserve_after // 2,
                                       int(round(atk_reserve_after * atk_strat.da_bonus_frac / 2))))
            else:
                atk_bonus = 0

            if dm == Maneuver.DODGE:
                def_fu = choose_dodge_roll(def_strat, def_reserve_after, 'def', am, is_low_threat)
            else:
                def_fu = 0

            atk_evasive = 0
            def_evasive = 0
            if am == Maneuver.DODGE and dm == Maneuver.COUNTER:
                atk_dodger_reserve = max(0, atk_reserve_after - atk_fu)
                atk_evasive = _int_commit(atk_strat.evasive_atk_frac, atk_dodger_reserve, min_val=0)
            if dm == Maneuver.DODGE and am in (Maneuver.SIMPLE_ATTACK,
                                               Maneuver.DECEPTIVE_ATTACK,
                                               Maneuver.FEINT):
                def_dodger_reserve = max(0, def_reserve_after - def_fu)
                ev_frac = (def_strat.evasive_vs_low_frac if is_low_threat
                           else def_strat.evasive_vs_high_frac)
                def_evasive = _int_commit(ev_frac, def_dodger_reserve, min_val=0)

            if track_stats:
                stats['total_exchanges'] += 1
                pair_key = f"{_letter(am)}_vs_{_letter(dm)}"
                if pair_key in stats['maneuvers']:
                    stats['maneuvers'][pair_key] += 1
                if am == Maneuver.SIMPLE_ATTACK:
                    stats['commits_by_maneuver']['SA'].append(ac)
                elif am == Maneuver.FEINT:
                    stats['commits_by_maneuver']['F'].append(ac)
                elif am == Maneuver.DECEPTIVE_ATTACK:
                    stats['commits_by_maneuver']['DA'].append(ac)
                    stats['commits_by_maneuver']['DA_BONUS'].append(atk_bonus)
                else:  # DODGE
                    stats['commits_by_maneuver']['D'].append(ac)
                    stats['commits_by_maneuver']['DR'].append(atk_fu)
                if dm == Maneuver.PARRY:
                    stats['commits_by_maneuver']['P'].append(dc)
                elif dm == Maneuver.COUNTER:
                    stats['commits_by_maneuver']['C'].append(dc)
                else:  # DODGE
                    stats['commits_by_maneuver']['D'].append(dc)
                    stats['commits_by_maneuver']['DR'].append(def_fu)
                if atk_evasive > 0:
                    stats['commits_by_maneuver']['EA'].append(atk_evasive)
                if def_evasive > 0:
                    stats['commits_by_maneuver']['EA'].append(def_evasive)

            result = resolve_exchange(atk_state, def_state, ac, dc, am, dm,
                                      atk_followup_commit=atk_fu,
                                      def_followup_commit=def_fu,
                                      atk_bonus=atk_bonus,
                                      atk_evasive_commit=atk_evasive,
                                      def_evasive_commit=def_evasive)
            if track_stats:
                for dmg in (result.attacker_damage_taken, result.defender_damage_taken):
                    if dmg > 0:
                        stats['hit_damages'].append(dmg)
                        if dmg > stats['bout_max_damage']:
                            stats['bout_max_damage'] = dmg
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
