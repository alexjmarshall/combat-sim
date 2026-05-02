"""
V4 combat rules. Substantial rewrite aimed at making mixing emerge.
"""

import random
from dataclasses import dataclass
from enum import Enum

# Advanced Maneuvers
RIPOSTE = False
STOP_HIT = False          # Counter deals extra damage equal to attacker's successes when it wins
DECEPTIVE_ATTACK = False  # Attacker may pump bonus dice into exchange at 2-for-1 reserve cost
EVASIVE_ATTACK = False    # Successful dodger makes a free unopposed attack from remaining reserve

WEAPON_BONUS = 2  # Max damage bonus for attacker; scales +1 per die committed up to this cap
ARMOR_BONUS = 2   # Extra successes for defender on each exchange


class Maneuver(Enum):
    PARRY = "Parry"
    COUNTER = "Counter"
    SIMPLE_ATTACK = "SimpleAttack"
    FEINT = "Feint"
    DODGE = "Dodge"
    DECEPTIVE_ATTACK = "DeceptiveAttack"
    DEFENSELESS = "Defenseless"


@dataclass
class CombatantState:
    max_hd: int
    reserve: int
    exchange: int = 0
    used: int = 0
    lost: int = 0

    @property
    def total_hd(self):
        return self.max_hd - self.lost

    def refresh(self):
        self.reserve = self.total_hd
        self.used = 0
        self.exchange = 0

    def commit(self, dice):
        dice = min(dice, self.reserve)
        self.reserve -= dice
        self.exchange += dice
        return dice
    
    def clear_exchange_to_used(self):
        self.used += self.exchange
        self.exchange = 0
    
    def apply_damage_default(self, damage):
        remaining = damage
        applied = 0
        from_exchange = min(remaining, self.exchange)
        self.exchange -= from_exchange
        self.lost += from_exchange
        remaining -= from_exchange
        applied += from_exchange
        if remaining > 0:
            from_reserve = min(remaining, self.reserve)
            self.reserve -= from_reserve
            self.lost += from_reserve
            remaining -= from_reserve
            applied += from_reserve
        if remaining > 0:
            from_used = min(remaining, self.used)
            self.used -= from_used
            self.lost += from_used
            applied += from_used
        return applied


def roll_successes(num_dice):
    if num_dice <= 0:
        return 0
    return sum(1 for _ in range(num_dice) if random.randint(1, 6) >= 5)


@dataclass
class ExchangeResult:
    attacker_damage_taken: int = 0
    defender_damage_taken: int = 0



def _evasive_attack(dodger, target, evasive_commit):
    if not EVASIVE_ATTACK or evasive_commit <= 0:
        return 0
    committed = dodger.commit(evasive_commit)
    if committed <= 0:
        return 0
    successes = roll_successes(committed)
    damage = max(0, successes + min(WEAPON_BONUS, committed) - ARMOR_BONUS) if successes > 0 else 0
    applied = target.apply_damage_default(damage)
    dodger.clear_exchange_to_used()
    return applied


def _resolve_dodge(attacker, defender, atk_commit, def_commit,
                   atk_maneuver, def_maneuver,
                   atk_followup_commit, def_followup_commit,
                   atk_evasive_commit, def_evasive_commit, result):
    # Phase 1: dodger(s) clear their initial commit to used.
    if atk_maneuver == Maneuver.DODGE:
        attacker.clear_exchange_to_used()
    if def_maneuver == Maneuver.DODGE:
        defender.clear_exchange_to_used()

    # Pairings with no incoming damage either way.
    if atk_maneuver == Maneuver.DODGE and def_maneuver in (Maneuver.DODGE, Maneuver.PARRY):
        if def_maneuver == Maneuver.PARRY:
            defender.clear_exchange_to_used()
        return result
    if def_maneuver == Maneuver.DODGE and atk_maneuver == Maneuver.DODGE:
        return result

    # SA / DA (atk) vs Dodge (def)
    if atk_maneuver in (Maneuver.SIMPLE_ATTACK, Maneuver.DECEPTIVE_ATTACK) and def_maneuver == Maneuver.DODGE:
        atk_successes = roll_successes(attacker.exchange)
        defender.commit(def_followup_commit)
        dodge_roll = roll_successes(defender.exchange)
        if dodge_roll >= max(1, ARMOR_BONUS):
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
            result.attacker_damage_taken += _evasive_attack(defender, attacker, def_evasive_commit)
        else:
            damage = max(0, atk_successes + min(WEAPON_BONUS, attacker.exchange) - ARMOR_BONUS) if atk_successes > 0 else 0
            result.defender_damage_taken = defender.apply_damage_default(damage)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
        return result

    # Counter (def) vs Dodge (atk)
    if atk_maneuver == Maneuver.DODGE and def_maneuver == Maneuver.COUNTER:
        attacker.commit(atk_followup_commit)
        dodge_roll = roll_successes(attacker.exchange)
        def_successes = roll_successes(def_commit)
        if dodge_roll >= max(1, ARMOR_BONUS):
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
            result.defender_damage_taken += _evasive_attack(attacker, defender, atk_evasive_commit)
        else:
            damage = max(0, def_successes + min(WEAPON_BONUS, defender.exchange) - ARMOR_BONUS) if def_successes > 0 else 0
            result.attacker_damage_taken = attacker.apply_damage_default(damage)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
        return result

    # Feint (atk) vs Dodge (def)
    if atk_maneuver == Maneuver.FEINT and def_maneuver == Maneuver.DODGE:
        attacker.clear_exchange_to_used()
        followup = min(atk_followup_commit, attacker.reserve)
        attacker.commit(followup)
        followup_successes = roll_successes(followup)
        defender.commit(def_followup_commit)
        dodge_roll = roll_successes(defender.exchange)
        if dodge_roll >= max(1, ARMOR_BONUS):
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
            result.attacker_damage_taken += _evasive_attack(defender, attacker, def_evasive_commit)
        else:
            damage = max(0, followup_successes + min(WEAPON_BONUS, attacker.exchange) - ARMOR_BONUS) if followup_successes > 0 else 0
            result.defender_damage_taken = defender.apply_damage_default(damage)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
        return result

    return result


def resolve_exchange(attacker, defender, atk_commit, def_commit,
                     atk_maneuver, def_maneuver,
                     atk_followup_commit=0, def_followup_commit=0,
                     atk_bonus=0,
                     atk_evasive_commit=0, def_evasive_commit=0):
    result = ExchangeResult()
    attacker.commit(atk_commit)
    defender.commit(def_commit)

    if def_maneuver == Maneuver.DEFENSELESS:
        def_maneuver = Maneuver.PARRY

    if atk_maneuver == Maneuver.DECEPTIVE_ATTACK and DECEPTIVE_ATTACK:
        bonus = max(0, min(atk_bonus, attacker.reserve // 2))
        attacker.reserve -= 2 * bonus
        attacker.exchange += bonus
        attacker.used += bonus

    if atk_maneuver == Maneuver.DODGE or def_maneuver == Maneuver.DODGE:
        return _resolve_dodge(attacker, defender, atk_commit, def_commit,
                              atk_maneuver, def_maneuver,
                              atk_followup_commit, def_followup_commit,
                              atk_evasive_commit, def_evasive_commit, result)

    if atk_maneuver in (Maneuver.SIMPLE_ATTACK, Maneuver.DECEPTIVE_ATTACK):
        atk_rolled = attacker.exchange
        atk_successes = roll_successes(atk_rolled)

        if def_maneuver == Maneuver.PARRY:
            def_rolled = defender.exchange
            def_successes = roll_successes(def_rolled)
            if atk_successes > def_successes:
                damage = max(0, (atk_successes - def_successes) + min(WEAPON_BONUS, atk_rolled) - ARMOR_BONUS)
            else:
                damage = 0
            result.defender_damage_taken = defender.apply_damage_default(damage)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
            if RIPOSTE and def_successes > atk_successes:
                riposte_damage = max(0, (def_successes - atk_successes) + min(WEAPON_BONUS, def_rolled) - ARMOR_BONUS)
                if riposte_damage > 0:
                    result.attacker_damage_taken = attacker.apply_damage_default(riposte_damage)

        elif def_maneuver == Maneuver.COUNTER:
            total_atk_dmg = max(0, atk_successes + min(WEAPON_BONUS, atk_rolled) - ARMOR_BONUS) if atk_successes > 0 else 0
            dmg_to_exchange = min(total_atk_dmg, defender.exchange)
            defender.exchange -= dmg_to_exchange
            defender.lost += dmg_to_exchange
            remaining_atk_dmg = total_atk_dmg - dmg_to_exchange
            if remaining_atk_dmg > 0:
                defender.apply_damage_default(remaining_atk_dmg)
            result.defender_damage_taken = atk_successes
            if defender.total_hd > 0 and defender.exchange > 0:
                def_successes = roll_successes(defender.exchange)
                stop_hit_bonus = atk_successes if (STOP_HIT and def_successes >= atk_successes) else 0
                counter_dmg = max(0, def_successes + min(WEAPON_BONUS, defender.exchange) - ARMOR_BONUS + stop_hit_bonus) if def_successes > 0 else 0
                result.attacker_damage_taken = attacker.apply_damage_default(counter_dmg)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()

    elif atk_maneuver == Maneuver.FEINT:
        attacker.clear_exchange_to_used()
        max_followup = def_commit  # follow-up cannot exceed def commit
                
        if def_maneuver == Maneuver.PARRY:
            defender.clear_exchange_to_used()
            followup = min(atk_followup_commit, attacker.reserve, max_followup)
            if followup > 0:
                attacker.commit(followup)
                followup_successes = roll_successes(followup)
                damage = max(0, followup_successes + min(WEAPON_BONUS, attacker.exchange) - ARMOR_BONUS) if followup_successes > 0 else 0
                result.defender_damage_taken = defender.apply_damage_default(damage)
                attacker.clear_exchange_to_used()

        elif def_maneuver == Maneuver.COUNTER:
            followup = min(atk_followup_commit, attacker.reserve, max_followup)
            attacker.commit(followup)
            def_successes = roll_successes(def_commit)
            total_counter_dmg = max(0, def_successes + min(WEAPON_BONUS, defender.exchange) - ARMOR_BONUS) if def_successes > 0 else 0
            dmg_to_exchange = min(total_counter_dmg, attacker.exchange)
            attacker.exchange -= dmg_to_exchange
            attacker.lost += dmg_to_exchange
            remaining_def_dmg = total_counter_dmg - dmg_to_exchange
            if remaining_def_dmg > 0:
                attacker.apply_damage_default(remaining_def_dmg)
            result.attacker_damage_taken = def_successes
            if attacker.total_hd > 0 and attacker.exchange > 0:
                fu_successes = roll_successes(attacker.exchange)
                dmg = max(0, fu_successes + min(WEAPON_BONUS, attacker.exchange) - ARMOR_BONUS) if fu_successes > 0 else 0
                result.defender_damage_taken = defender.apply_damage_default(dmg)
            attacker.clear_exchange_to_used()
            defender.clear_exchange_to_used()
    
    return result
