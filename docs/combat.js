import { rollSuccesses } from "./rng.js";

export const Maneuver = Object.freeze({
  PARRY: "Parry",
  COUNTER: "Counter",
  SIMPLE_ATTACK: "SimpleAttack",
  FEINT: "Feint",
  DODGE: "Dodge",
  DECEPTIVE_ATTACK: "DeceptiveAttack",
  DEFENSELESS: "Defenseless",
});

export class CombatantState {
  constructor(maxHd) {
    this.maxHd = maxHd;
    this.reserve = maxHd;
    this.exchange = 0;
    this.used = 0;
    this.lost = 0;
    this.phantom = 0; // temporarily unavailable dice (initiative penalty); drains to lost if hit
  }

  get totalHd() {
    return this.maxHd - this.lost;
  }

  refresh() {
    this.reserve = this.totalHd;
    this.used = 0;
    this.exchange = 0;
    this.phantom = 0;
  }

  commit(dice) {
    dice = Math.min(dice, this.reserve);
    this.reserve -= dice;
    this.exchange += dice;
    return dice;
  }

  clearExchangeToUsed() {
    this.used += this.exchange;
    this.exchange = 0;
  }

  applyDamageDefault(damage) {
    let remaining = damage < 2 ? damage : damage * 3; // TEST
    let applied = 0;
    const fromExchange = Math.min(remaining, this.exchange);
    this.exchange -= fromExchange;
    this.lost += fromExchange;
    remaining -= fromExchange;
    applied += fromExchange;
    if (remaining > 0) {
      const fromReserve = Math.min(remaining, this.reserve);
      this.reserve -= fromReserve;
      this.lost += fromReserve;
      remaining -= fromReserve;
      applied += fromReserve;
    }
    if (remaining > 0) {
      const fromUsed = Math.min(remaining, this.used);
      this.used -= fromUsed;
      this.lost += fromUsed;
      remaining -= fromUsed;
      applied += fromUsed;
    }
    if (remaining > 0) {
      const fromPhantom = Math.min(remaining, this.phantom);
      this.phantom -= fromPhantom;
      this.lost += fromPhantom;
      applied += fromPhantom;
    }
    return applied;
  }
}

export function ExchangeResult() {
  return {
    attackerDamageTaken: 0,
    defenderDamageTaken: 0,
    atkRolled: 0,
    defRolled: 0,
    atkSuccesses: 0,
    defSuccesses: 0,
    followupRolled: 0,
    followupSuccesses: 0,
    dodgeRolled: 0,
    dodgeSuccesses: 0,
    dodgeSucceeded: false,
  };
}

function _evasiveAttack(dodger, target, evasiveCommit, flags) {
  const { evasiveAttack, weaponBonus, armorBonus } = flags;
  if (!evasiveAttack || evasiveCommit <= 0) return 0;
  const committed = dodger.commit(evasiveCommit);
  if (committed <= 0) return 0;
  const successes = rollSuccesses(committed);
  const damage =
    successes > 0
      ? Math.max(0, successes + Math.min(weaponBonus, committed) - armorBonus)
      : 0;
  const applied = target.applyDamageDefault(damage);
  dodger.clearExchangeToUsed();
  return applied;
}

function _resolveDodge(
  attacker,
  defender,
  atkCommit,
  defCommit,
  atkManeuver,
  defManeuver,
  atkFollowupCommit,
  defFollowupCommit,
  atkEvasiveCommit,
  defEvasiveCommit,
  result,
  flags,
) {
  const { armorBonus, weaponBonus } = flags;

  if (atkManeuver === Maneuver.DODGE) attacker.clearExchangeToUsed();
  if (defManeuver === Maneuver.DODGE) defender.clearExchangeToUsed();

  if (
    atkManeuver === Maneuver.DODGE &&
    (defManeuver === Maneuver.DODGE || defManeuver === Maneuver.PARRY)
  ) {
    if (defManeuver === Maneuver.PARRY) defender.clearExchangeToUsed();
    return result;
  }
  if (defManeuver === Maneuver.DODGE && atkManeuver === Maneuver.DODGE) {
    return result;
  }

  // SA / DA (atk) vs Dodge (def)
  if (
    (atkManeuver === Maneuver.SIMPLE_ATTACK ||
      atkManeuver === Maneuver.DECEPTIVE_ATTACK) &&
    defManeuver === Maneuver.DODGE
  ) {
    result.atkRolled = attacker.exchange;
    const atkSuccesses = rollSuccesses(attacker.exchange);
    result.atkSuccesses = atkSuccesses;
    defender.commit(defFollowupCommit);
    result.dodgeRolled = defender.exchange;
    const dodgeRoll = rollSuccesses(defender.exchange);
    result.dodgeSuccesses = dodgeRoll;
    const atkDiceForBonus = attacker.exchange;
    if (dodgeRoll >= Math.max(1, armorBonus)) {
      result.dodgeSucceeded = true;
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
      result.attackerDamageTaken += _evasiveAttack(
        defender,
        attacker,
        defEvasiveCommit,
        flags,
      );
    } else {
      const damage =
        atkSuccesses > 0
          ? Math.max(
              0,
              atkSuccesses +
                Math.min(weaponBonus, atkDiceForBonus) -
                armorBonus,
            )
          : 0;
      result.defenderDamageTaken = defender.applyDamageDefault(damage);
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
    }
    return result;
  }

  // Counter (def) vs Dodge (atk)
  if (atkManeuver === Maneuver.DODGE && defManeuver === Maneuver.COUNTER) {
    attacker.commit(atkFollowupCommit);
    result.dodgeRolled = attacker.exchange;
    const dodgeRoll = rollSuccesses(attacker.exchange);
    result.dodgeSuccesses = dodgeRoll;
    result.defRolled = defCommit;
    const defSuccesses = rollSuccesses(defCommit);
    result.defSuccesses = defSuccesses;
    const defDiceForBonus = defender.exchange;
    if (dodgeRoll >= Math.max(1, armorBonus)) {
      result.dodgeSucceeded = true;
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
      result.defenderDamageTaken += _evasiveAttack(
        attacker,
        defender,
        atkEvasiveCommit,
        flags,
      );
    } else {
      const damage =
        defSuccesses > 0
          ? Math.max(
              0,
              defSuccesses +
                Math.min(weaponBonus, defDiceForBonus) -
                armorBonus,
            )
          : 0;
      result.attackerDamageTaken = attacker.applyDamageDefault(damage);
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
    }
    return result;
  }

  // Feint (atk) vs Dodge (def)
  if (atkManeuver === Maneuver.FEINT && defManeuver === Maneuver.DODGE) {
    attacker.clearExchangeToUsed();
    attacker.commit(atkFollowupCommit);
    result.followupRolled = atkFollowupCommit;
    const followupSuccesses = rollSuccesses(atkFollowupCommit);
    result.followupSuccesses = followupSuccesses;
    defender.commit(defFollowupCommit);
    result.dodgeRolled = defender.exchange;
    const dodgeRoll = rollSuccesses(defender.exchange);
    result.dodgeSuccesses = dodgeRoll;
    const atkDiceForBonus = attacker.exchange;
    if (dodgeRoll >= Math.max(1, armorBonus)) {
      result.dodgeSucceeded = true;
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
      result.attackerDamageTaken += _evasiveAttack(
        defender,
        attacker,
        defEvasiveCommit,
        flags,
      );
    } else {
      const damage =
        followupSuccesses > 0
          ? Math.max(
              0,
              followupSuccesses +
                Math.min(weaponBonus, atkDiceForBonus) -
                armorBonus,
            )
          : 0;
      result.defenderDamageTaken = defender.applyDamageDefault(damage);
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
    }
    return result;
  }

  return result;
}

export function resolveExchange(opts) {
  const {
    attacker,
    defender,
    atkCommit,
    defCommit,
    atkManeuver,
    defManeuver,
    atkFollowupCommit = 0,
    defFollowupCommit = 0,
    atkBonus = 0,
    atkEvasiveCommit = 0,
    defEvasiveCommit = 0,
    weaponBonus = 3,
    armorBonus = 3,
    riposte = false,
    stopHit = false,
    deceptiveAttack = false,
    evasiveAttack = false,
  } = opts;

  const flags = { weaponBonus, armorBonus, evasiveAttack };

  const result = ExchangeResult();
  attacker.commit(atkCommit);
  defender.commit(defCommit);

  let defM =
    defManeuver === Maneuver.DEFENSELESS ? Maneuver.PARRY : defManeuver;

  if (atkManeuver === Maneuver.DECEPTIVE_ATTACK && deceptiveAttack) {
    const bonus = Math.max(
      0,
      Math.min(atkBonus, Math.floor(attacker.reserve / 2)),
    );
    attacker.reserve -= 2 * bonus;
    attacker.exchange += bonus;
    attacker.used += bonus;
  }

  if (atkManeuver === Maneuver.DODGE || defM === Maneuver.DODGE) {
    return _resolveDodge(
      attacker,
      defender,
      atkCommit,
      defCommit,
      atkManeuver,
      defM,
      atkFollowupCommit,
      defFollowupCommit,
      atkEvasiveCommit,
      defEvasiveCommit,
      result,
      flags,
    );
  }

  if (
    atkManeuver === Maneuver.SIMPLE_ATTACK ||
    atkManeuver === Maneuver.DECEPTIVE_ATTACK
  ) {
    const atkRolled = attacker.exchange;
    const atkSuccesses = rollSuccesses(atkRolled);
    result.atkRolled = atkRolled;
    result.atkSuccesses = atkSuccesses;

    if (defM === Maneuver.PARRY) {
      const defRolled = defender.exchange;
      let defSuccesses = rollSuccesses(defRolled) * 2; // TEST;
      result.defRolled = defRolled;
      result.defSuccesses = defSuccesses;
      const damage =
        atkSuccesses > defSuccesses
          ? Math.max(
              0,
              atkSuccesses -
                defSuccesses +
                Math.min(weaponBonus, atkRolled) -
                armorBonus,
            )
          : 0;
      result.defenderDamageTaken = defender.applyDamageDefault(damage);
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
      defSuccesses = Math.floor(defSuccesses / 2); // TEST
      if (riposte && defSuccesses > atkSuccesses) {
        const riposteDamage = Math.max(
          0,
          defSuccesses -
            atkSuccesses +
            Math.min(weaponBonus, defRolled) -
            armorBonus,
        );
        if (riposteDamage > 0) {
          result.attackerDamageTaken =
            attacker.applyDamageDefault(riposteDamage);
        }
      }
    } else if (defM === Maneuver.COUNTER) {
      const totalAtkDmg =
        atkSuccesses > 0
          ? Math.max(
              0,
              atkSuccesses + Math.min(weaponBonus, atkRolled) - armorBonus,
            )
          : 0;
      result.defenderDamageTaken = defender.applyDamageDefault(totalAtkDmg);
      if (defender.totalHd > 0 && defender.exchange > 0) {
        const defRolled = defender.exchange;
        const defSuccesses = rollSuccesses(defRolled);
        result.defRolled = defRolled;
        result.defSuccesses = defSuccesses;
        const stopHitBonus =
          stopHit && defSuccesses >= atkSuccesses ? atkSuccesses : 0;
        const counterDmg =
          defSuccesses > 0
            ? Math.max(
                0,
                defSuccesses +
                  Math.min(weaponBonus, defender.exchange) -
                  armorBonus +
                  stopHitBonus,
              )
            : 0;
        result.attackerDamageTaken = attacker.applyDamageDefault(counterDmg);
      }
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
    }
  } else if (atkManeuver === Maneuver.FEINT) {
    attacker.clearExchangeToUsed();

    if (defM === Maneuver.PARRY) {
      defender.clearExchangeToUsed();
      if (atkFollowupCommit > 0) {
        attacker.commit(atkFollowupCommit);
        result.followupRolled = atkFollowupCommit;
        const followupSuccesses = rollSuccesses(atkFollowupCommit);
        result.followupSuccesses = followupSuccesses;
        const damage =
          followupSuccesses > 0
            ? Math.max(
                0,
                followupSuccesses +
                  Math.min(weaponBonus, attacker.exchange) -
                  armorBonus,
              )
            : 0;
        result.defenderDamageTaken = defender.applyDamageDefault(damage);
        attacker.clearExchangeToUsed();
      }
    } else if (defM === Maneuver.COUNTER) {
      attacker.commit(atkFollowupCommit);
      result.followupRolled = atkFollowupCommit;
      const defRolled = defCommit;
      const defSuccesses = rollSuccesses(defCommit);
      result.defRolled = defRolled;
      result.defSuccesses = defSuccesses;
      const totalCounterDmg =
        defSuccesses > 0
          ? Math.max(
              0,
              defSuccesses +
                Math.min(weaponBonus, defender.exchange) -
                armorBonus,
            )
          : 0;
      result.attackerDamageTaken = attacker.applyDamageDefault(totalCounterDmg);
      if (attacker.totalHd > 0 && attacker.exchange > 0) {
        const fuSuccesses = rollSuccesses(attacker.exchange);
        result.followupSuccesses = fuSuccesses;
        const dmg =
          fuSuccesses > 0
            ? Math.max(
                0,
                fuSuccesses +
                  Math.min(weaponBonus, attacker.exchange) -
                  armorBonus,
              )
            : 0;
        result.defenderDamageTaken = defender.applyDamageDefault(dmg);
      }
      attacker.clearExchangeToUsed();
      defender.clearExchangeToUsed();
    }
  }

  return result;
}
