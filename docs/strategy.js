import { rand } from "./rng.js";
import { Maneuver } from "./combat.js";

export function Strategy(fields = {}) {
  const defaults = {
    feintProb: 0.4,
    saCommitFrac: 0.5,
    feintCommitFrac: 0.2,
    feintFollowupVsParryFrac: 0.6,
    feintFollowupVsCounterFrac: 0.4,
    continueAfterHitDealtProb: 0.5,
    continueAfterWhiffProb: 0.8,
    dodgeProbAtk: 0.05,
    dodgeCommitAtkFrac: 0.1,
    dodgeRollAtkFrac: 0.4,
    daProb: 0.1,
    daCommitFrac: 0.4,
    daBonusFrac: 0.3,
    evasiveAtkFrac: 0.3,
    commitRatioThreshold: 0.5,
    counterProbVsLow: 0.5,
    parryCommitVsLowFrac: 0.3,
    counterCommitVsLowFrac: 0.4,
    counterProbVsHigh: 0.3,
    parryCommitVsHighFrac: 0.7,
    counterCommitVsHighFrac: 0.5,
    minReserveFracToContinue: 0.15,
    dodgeProbVsLow: 0.05,
    dodgeCommitVsLowFrac: 0.1,
    dodgeRollVsLowFrac: 0.3,
    dodgeProbVsHigh: 0.05,
    dodgeCommitVsHighFrac: 0.1,
    dodgeRollVsHighFrac: 0.5,
    evasiveVsLowFrac: 0.3,
    evasiveVsHighFrac: 0.3,
  };

  const s = { ...defaults, ...fields };

  s.clip = function () {
    const c = (x, lo = 0.01, hi = 0.99) => Math.max(lo, Math.min(hi, x));
    return Strategy({
      feintProb: c(this.feintProb),
      saCommitFrac: c(this.saCommitFrac),
      feintCommitFrac: c(this.feintCommitFrac),
      feintFollowupVsParryFrac: c(this.feintFollowupVsParryFrac),
      feintFollowupVsCounterFrac: c(this.feintFollowupVsCounterFrac),
      continueAfterHitDealtProb: c(this.continueAfterHitDealtProb),
      continueAfterWhiffProb: c(this.continueAfterWhiffProb),
      dodgeProbAtk: c(this.dodgeProbAtk),
      dodgeCommitAtkFrac: c(this.dodgeCommitAtkFrac),
      dodgeRollAtkFrac: c(this.dodgeRollAtkFrac),
      daProb: c(this.daProb),
      daCommitFrac: c(this.daCommitFrac),
      daBonusFrac: c(this.daBonusFrac),
      evasiveAtkFrac: c(this.evasiveAtkFrac),
      commitRatioThreshold: c(this.commitRatioThreshold),
      counterProbVsLow: c(this.counterProbVsLow),
      parryCommitVsLowFrac: c(this.parryCommitVsLowFrac),
      counterCommitVsLowFrac: c(this.counterCommitVsLowFrac),
      counterProbVsHigh: c(this.counterProbVsHigh),
      parryCommitVsHighFrac: c(this.parryCommitVsHighFrac),
      counterCommitVsHighFrac: c(this.counterCommitVsHighFrac),
      minReserveFracToContinue: c(this.minReserveFracToContinue, 0.05, 0.6),
      dodgeProbVsLow: c(this.dodgeProbVsLow),
      dodgeCommitVsLowFrac: c(this.dodgeCommitVsLowFrac),
      dodgeRollVsLowFrac: c(this.dodgeRollVsLowFrac),
      dodgeProbVsHigh: c(this.dodgeProbVsHigh),
      dodgeCommitVsHighFrac: c(this.dodgeCommitVsHighFrac),
      dodgeRollVsHighFrac: c(this.dodgeRollVsHighFrac),
      evasiveVsLowFrac: c(this.evasiveVsLowFrac),
      evasiveVsHighFrac: c(this.evasiveVsHighFrac),
    });
  };

  return s;
}

export function makeAiStrategy(difficulty) {
  const s = Strategy();
  if (difficulty === "easy") {
    s.feintProb = 0.10;
    s.saCommitFrac = 0.35;
    s.dodgeProbAtk = 0.02;
  } else if (difficulty === "hard") {
    s.feintProb = 0.55;
    s.saCommitFrac = 0.60;
    s.dodgeProbAtk = 0.08;
  }
  const clipped = s.clip();
  clipped.difficulty = difficulty;
  clipped.mediumHeuristicProb = 0.6;
  return clipped;
}

function _heuristicsActive(strat) {
  if (strat.difficulty === "hard") return true;
  if (strat.difficulty === "medium") return rand() < strat.mediumHeuristicProb;
  return false;
}

function _intCommit(fraction, reserve, minVal = 1) {
  if (reserve <= 0) return 0;
  return Math.max(minVal, Math.min(reserve, Math.round(reserve * fraction)));
}

// Tentative attacker maneuver chosen at commit time (before seeing defender's
// commit). The session calls chooseAtkManeuver later — once def_commit is known —
// to either ratify the tentative pick or override it via tactical heuristics.
export function chooseAtkCommit(strat, attacker, deceptiveAttack = false) {
  const r = rand();
  const pDodge = strat.dodgeProbAtk;
  const pFeint = (1 - pDodge) * strat.feintProb;
  const pDa = deceptiveAttack ? (1 - pDodge) * (1 - strat.feintProb) * strat.daProb : 0;
  if (r < pDodge) {
    return [_intCommit(strat.dodgeCommitAtkFrac, attacker.reserve), Maneuver.DODGE];
  }
  if (r < pDodge + pFeint) {
    return [_intCommit(strat.feintCommitFrac, attacker.reserve), Maneuver.FEINT];
  }
  if (r < pDodge + pFeint + pDa) {
    return [_intCommit(strat.daCommitFrac, attacker.reserve), Maneuver.DECEPTIVE_ATTACK];
  }
  return [_intCommit(strat.saCommitFrac, attacker.reserve), Maneuver.SIMPLE_ATTACK];
}

export function chooseAtkManeuver(strat, attacker, atkCommit, defCommit, tentative) {
  if (!_heuristicsActive(strat)) return tentative;
  const reserveAfterCommit = attacker.reserve - atkCommit;

  // Rule: dodge if defender's commit is much larger AND we have >=3 dice for the
  // dodge follow-up roll.
  if (defCommit >= atkCommit * 2 && reserveAfterCommit >= 3) {
    return Maneuver.DODGE;
  }
  // Rule: feint if we committed a small amount AND defender's commit is equal or
  // only slightly larger.
  const smallCommit = Math.max(2, Math.round(attacker.maxHd * 0.25));
  if (atkCommit <= smallCommit && defCommit >= atkCommit && defCommit <= atkCommit + 2) {
    return Maneuver.FEINT;
  }
  return tentative;
}

export function chooseDefense(strat, defender, atkCommit) {
  if (defender.reserve <= 0) return [Maneuver.DEFENSELESS, 0];
  const commitRatio = atkCommit / Math.max(1, defender.reserve);
  const isLow = commitRatio < strat.commitRatioThreshold;

  if (_heuristicsActive(strat)) {
    const counterFrac = isLow ? strat.counterCommitVsLowFrac : strat.counterCommitVsHighFrac;
    const parryFrac = isLow ? strat.parryCommitVsLowFrac : strat.parryCommitVsHighFrac;
    const dodgeFrac = isLow ? strat.dodgeCommitVsLowFrac : strat.dodgeCommitVsHighFrac;
    const counterCommit = _intCommit(counterFrac, defender.reserve);
    const dodgeCommit = _intCommit(dodgeFrac, defender.reserve);
    const parryCommit = _intCommit(parryFrac, defender.reserve);

    // Rule: counter if our commit beats the attacker's.
    if (counterCommit > atkCommit) {
      return [Maneuver.COUNTER, counterCommit];
    }
    // Rule: dodge if our parry would be lower than attacker's commit AND we have
    // >=3 dice left for the dodge follow-up roll.
    if (parryCommit < atkCommit && defender.reserve - dodgeCommit >= 3) {
      return [Maneuver.DODGE, dodgeCommit];
    }
    return [Maneuver.PARRY, parryCommit];
  }

  if (isLow) {
    if (rand() < strat.dodgeProbVsLow) {
      return [Maneuver.DODGE, _intCommit(strat.dodgeCommitVsLowFrac, defender.reserve)];
    }
    if (rand() < strat.counterProbVsLow) {
      return [Maneuver.COUNTER, _intCommit(strat.counterCommitVsLowFrac, defender.reserve)];
    }
    return [Maneuver.PARRY, _intCommit(strat.parryCommitVsLowFrac, defender.reserve)];
  } else {
    if (rand() < strat.dodgeProbVsHigh) {
      return [Maneuver.DODGE, _intCommit(strat.dodgeCommitVsHighFrac, defender.reserve)];
    }
    if (rand() < strat.counterProbVsHigh) {
      return [Maneuver.COUNTER, _intCommit(strat.counterCommitVsHighFrac, defender.reserve)];
    }
    return [Maneuver.PARRY, _intCommit(strat.parryCommitVsHighFrac, defender.reserve)];
  }
}

export function chooseFollowup(strat, reserveAfterCommit, defManeuver) {
  const frac = defManeuver === Maneuver.PARRY
    ? strat.feintFollowupVsParryFrac
    : strat.feintFollowupVsCounterFrac;
  return Math.max(0, Math.min(reserveAfterCommit, Math.round(reserveAfterCommit * frac)));
}

export function chooseDodgeRoll(strat, reserveAfterCommit, side, oppManeuver, isLowThreat = false) {
  if (reserveAfterCommit <= 0) return 0;
  if (oppManeuver === Maneuver.DODGE || oppManeuver === Maneuver.PARRY) return 0;
  const frac = side === "atk"
    ? strat.dodgeRollAtkFrac
    : (isLowThreat ? strat.dodgeRollVsLowFrac : strat.dodgeRollVsHighFrac);
  return Math.max(0, Math.min(reserveAfterCommit, Math.round(reserveAfterCommit * frac)));
}

export function decideContinue(strat, result, attacker) {
  if (attacker.reserve <= Math.max(1, Math.trunc(attacker.maxHd * strat.minReserveFracToContinue))) {
    return false;
  }
  if (result.defenderDamageTaken > 0) {
    return rand() < strat.continueAfterHitDealtProb;
  }
  return rand() < strat.continueAfterWhiffProb;
}
