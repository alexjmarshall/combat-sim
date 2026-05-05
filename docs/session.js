import { CombatantState, Maneuver, resolveExchange } from "./combat.js";
import { makeAiStrategy, chooseAtkCommit, chooseAtkManeuver, chooseDefense, chooseFollowup, chooseDodgeRoll, decideContinue } from "./strategy.js";

export const Phase = Object.freeze({
  IDLE: "idle",
  AWAIT_ATK_COMMIT: "await_atk_commit",
  AWAIT_DEF_COMMIT: "await_def_commit",
  AWAIT_ATK_MANEUVER: "await_atk_maneuver",
  AWAIT_DEF_MANEUVER: "await_def_maneuver",
  AWAIT_CONTINUE: "await_continue",
  GAME_OVER: "game_over",
});

const _MANEUVER_NAMES = {
  [Maneuver.SIMPLE_ATTACK]: "Attack",
  [Maneuver.FEINT]: "Feint",
  [Maneuver.DODGE]: "Dodge",
  [Maneuver.PARRY]: "Parry",
  [Maneuver.COUNTER]: "Counter",
  [Maneuver.DEFENSELESS]: "Defenseless",
};

function _maneuverLabel(m) {
  return _MANEUVER_NAMES[m] ?? m;
}

export class GameSession {
  constructor() {
    this.phase = Phase.IDLE;
    this.settings = null;
    this.states = [];
    this.humanIdx = 0;
    this.attackerIdx = 0;
    this.turn = 0;
    this.exchangeInTurn = 0;
    this.log = [];
    this.lastExchange = null;
    this.winnerIdx = null;
    this._aiStrategy = null;

    this._atkCommit = 0;
    this._defCommit = 0;
    this._atkManeuver = null;
    this._defManeuver = null;
    this._atkFollowup = 0;
    this._defFollowup = 0;
    this._atkTentative = null;

    this._aiContinueDecision = null;
    this._forceEndTurn = false;
  }

  // ---- public API -------------------------------------------------------

  newGame(settings) {
    this.settings = settings;
    this._aiStrategy = makeAiStrategy(settings.ai_difficulty);
    const hd = settings.combatant_dice;
    this.states = [new CombatantState(hd), new CombatantState(hd)];

    let initiativeWinner;
    if (settings.human_role === "attacker") {
      this.humanIdx = 0;
      initiativeWinner = 0;
    } else if (settings.human_role === "defender") {
      this.humanIdx = 0;
      initiativeWinner = 1;
    } else {
      this.humanIdx = Math.random() < 0.5 ? 0 : 1;
      initiativeWinner = Math.random() < 0.5 ? 0 : 1;
    }

    this.attackerIdx = initiativeWinner;
    const loserIdx = 1 - initiativeWinner;
    const loser = this.states[loserIdx];
    const availableHd = Math.ceil(hd * settings.initiative_loser_penalty);
    loser.reserve = availableHd;
    loser.phantom = hd - availableHd;

    this.turn = 0;
    this.exchangeInTurn = 0;
    this.log = [];
    this.lastExchange = null;
    this.winnerIdx = null;
    this._resetPending();
    this._aiContinueDecision = null;

    this._log({
      kind: "game_start",
      human_idx: this.humanIdx,
      initiative_winner: initiativeWinner,
      settings: { ...settings },
    });
    this._beginTurn(true);
  }

  submitAtkCommit(body) {
    const { n = null, end_turn = false } = body;
    this._requirePhase(Phase.AWAIT_ATK_COMMIT);
    this._requireHumanIs(this.attackerIdx);
    const atkState = this.states[this.attackerIdx];
    if (end_turn) {
      this._endTurn();
      return;
    }
    if (n === null) throw new Error("Must provide n or end_turn=true");
    if (n < 1 || n > atkState.reserve) throw new Error(`atk_commit must be in [1, ${atkState.reserve}]`);
    this._atkCommit = n;
    const defIdx = 1 - this.attackerIdx;
    const [dm, dc] = chooseDefense(this._aiStrategy, this.states[defIdx], n);
    this._defManeuver = dm;
    this._defCommit = Math.max(0, Math.min(dc, this.states[defIdx].reserve));
    this.phase = Phase.AWAIT_ATK_MANEUVER;
  }

  submitDefCommit(n) {
    this._requirePhase(Phase.AWAIT_DEF_COMMIT);
    this._requireHumanIs(1 - this.attackerIdx);
    const defState = this.states[1 - this.attackerIdx];
    if (n < 0 || n > defState.reserve) throw new Error(`def_commit must be in [0, ${defState.reserve}]`);
    this._defCommit = n;
    if (this._atkManeuver === null) {
      const atkState = this.states[this.attackerIdx];
      this._atkManeuver = chooseAtkManeuver(this._aiStrategy, atkState, this._atkCommit, this._defCommit, this._atkTentative);
    }
    this.phase = Phase.AWAIT_DEF_MANEUVER;
  }

  submitAtkManeuver(body) {
    const { maneuver, followup = null, dodge_roll = null } = body;
    this._requirePhase(Phase.AWAIT_ATK_MANEUVER);
    this._requireHumanIs(this.attackerIdx);
    const m = this._parseAtkManeuver(maneuver);
    const atkState = this.states[this.attackerIdx];
    const reserveAfterCommit = atkState.reserve - this._atkCommit;

    let atkFollowup = 0;
    if (m === Maneuver.FEINT) {
      atkFollowup = Math.max(0, Math.min(reserveAfterCommit, parseInt(followup || 0, 10)));
    } else if (m === Maneuver.DODGE) {
      atkFollowup = Math.max(0, Math.min(reserveAfterCommit, parseInt(dodge_roll || 0, 10)));
    }

    this._atkManeuver = m;
    this._atkFollowup = atkFollowup;

    if (this._defManeuver === Maneuver.DODGE) {
      const defState = this.states[1 - this.attackerIdx];
      const reserveAfterDefCommit = defState.reserve - this._defCommit;
      const stratRoll = chooseDodgeRoll(this._aiStrategy, reserveAfterDefCommit, "def", m);
      const minimum = Math.floor(this._atkCommit / 2);
      this._defFollowup = Math.min(reserveAfterDefCommit, Math.max(stratRoll, minimum));
    }

    this._resolveNow();
  }

  submitDefManeuver(body) {
    const { maneuver, dodge_roll = null } = body;
    this._requirePhase(Phase.AWAIT_DEF_MANEUVER);
    this._requireHumanIs(1 - this.attackerIdx);
    const m = this._parseDefManeuver(maneuver);
    const defState = this.states[1 - this.attackerIdx];
    const reserveAfterCommit = defState.reserve - this._defCommit;

    let defFollowup = 0;
    if (m === Maneuver.DODGE) {
      defFollowup = Math.max(0, Math.min(reserveAfterCommit, parseInt(dodge_roll || 0, 10)));
    }

    this._defManeuver = m;
    this._defFollowup = defFollowup;

    // AI is attacker; its maneuver was stashed at exchange start. Compute its
    // follow-up now that it can see the defender's chosen maneuver.
    if (this._atkManeuver === Maneuver.FEINT) {
      const atkState = this.states[this.attackerIdx];
      const reserveAfterAtkCommit = atkState.reserve - this._atkCommit;
      this._atkFollowup = chooseFollowup(this._aiStrategy, reserveAfterAtkCommit, m);
    } else if (this._atkManeuver === Maneuver.DODGE) {
      const atkState = this.states[this.attackerIdx];
      const reserveAfterAtkCommit = atkState.reserve - this._atkCommit;
      const stratRoll = chooseDodgeRoll(this._aiStrategy, reserveAfterAtkCommit, "atk", m);
      const minimum = Math.floor(this._defCommit / 2);
      this._atkFollowup = Math.min(reserveAfterAtkCommit, Math.max(stratRoll, minimum));
    } else {
      this._atkFollowup = 0;
    }

    this._resolveNow();
  }

  submitContinue(cont = null) {
    this._requirePhase(Phase.AWAIT_CONTINUE);
    if (this.winnerIdx !== null) return;

    const forceEnd = this._forceEndTurn;
    this._forceEndTurn = false;
    if (forceEnd) {
      this._endTurn();
      return;
    }

    if (this.attackerIdx === this.humanIdx) {
      if (cont === null) throw new Error("Must provide continue: bool");
      if (cont && this.states[this.attackerIdx].reserve >= 1) {
        this._beginExchange();
      } else {
        this._endTurn();
      }
    } else {
      if (this._aiContinueDecision && this.states[this.attackerIdx].reserve >= 1) {
        this._beginExchange();
      } else {
        this._endTurn();
      }
    }
  }

  // ---- visible state ----------------------------------------------------

  toVisibleDict() {
    if (this.settings === null) {
      return { phase: Phase.IDLE };
    }

    const atkIdx = this.attackerIdx;
    const visible = {};

    if (this.phase === Phase.AWAIT_DEF_COMMIT || this.phase === Phase.AWAIT_DEF_MANEUVER) {
      visible.atk_commit = this._atkCommit;
    }
    if (this.phase === Phase.AWAIT_ATK_MANEUVER) {
      visible.def_commit = this._defCommit;
      if (this.settings.exchange_mode === "sequential" && this._defManeuver !== null) {
        visible.def_maneuver = _maneuverLabel(this._defManeuver);
      }
    }

    return {
      phase: this.phase,
      turn: this.turn,
      exchange_in_turn: this.exchangeInTurn,
      human_idx: this.humanIdx,
      attacker_idx: atkIdx,
      states: this.states.map(s => this._stateDict(s)),
      visible,
      prompt: this._currentPrompt(),
      last_exchange: this.lastExchange,
      log: this.log.slice(-200),
      winner_idx: this.winnerIdx,
      settings: { ...this.settings },
    };
  }

  // ---- internals --------------------------------------------------------

  _stateDict(s) {
    return {
      max_hd: s.maxHd,
      reserve: s.reserve,
      exchange: s.exchange,
      used: s.used,
      lost: s.lost,
      phantom: s.phantom,
      total_hd: s.totalHd,
    };
  }

  _resetPending() {
    this._atkCommit = 0;
    this._defCommit = 0;
    this._atkManeuver = null;
    this._defManeuver = null;
    this._atkFollowup = 0;
    this._defFollowup = 0;
    this._atkTentative = null;
  }

  _requirePhase(p) {
    if (this.phase !== p) {
      throw new Error(`phase mismatch: expected ${p}, current ${this.phase}`);
    }
  }

  _requireHumanIs(idx) {
    if (this.humanIdx !== idx) {
      throw new Error("not the human's turn for this action");
    }
  }

  _parseAtkManeuver(raw) {
    const m = (raw || "").toLowerCase();
    if (["attack", "simpleattack", "simple_attack", "sa"].includes(m)) return Maneuver.SIMPLE_ATTACK;
    if (["feint", "f"].includes(m)) return Maneuver.FEINT;
    if (["dodge", "d"].includes(m)) return Maneuver.DODGE;
    throw new Error(`invalid attacker maneuver: ${JSON.stringify(raw)}`);
  }

  _parseDefManeuver(raw) {
    const m = (raw || "").toLowerCase();
    if (["parry", "p"].includes(m)) return Maneuver.PARRY;
    if (["counter", "c"].includes(m)) return Maneuver.COUNTER;
    if (["dodge", "d"].includes(m)) return Maneuver.DODGE;
    throw new Error(`invalid defender maneuver: ${JSON.stringify(raw)}`);
  }

  _beginTurn(first = false) {
    this.turn += 1;
    this.exchangeInTurn = 0;
    const atkIdx = this.attackerIdx;
    const atkState = this.states[atkIdx];
    const defState = this.states[1 - atkIdx];

    if (!first) {
      if (this.settings.refresh_start_of_turn) atkState.refresh();
      if (this.settings.refresh_end_of_turn) defState.refresh();
    }

    this._log({ kind: "turn_start", turn: this.turn, attacker_idx: atkIdx });

    if (atkState.reserve < 1 && defState.reserve < 1) {
      if (this.turn >= 60) { this._enterGameOver(null); return; }
      this._endTurn();
      return;
    }

    this._beginExchange();
  }

  _beginExchange() {
    this._resetPending();
    this._aiContinueDecision = null;
    this.exchangeInTurn += 1;
    const atkIdx = this.attackerIdx;
    const atkState = this.states[atkIdx];
    const defState = this.states[1 - atkIdx];

    if (atkState.reserve < 1) { this._endTurn(); return; }

    if (atkIdx === this.humanIdx) {
      this.phase = Phase.AWAIT_ATK_COMMIT;
      return;
    }

    // AI attacker path. Pick the commit (and a tentative maneuver), but defer the
    // final maneuver choice until def_commit is known so heuristics can react.
    const [ac, tentative] = chooseAtkCommit(this._aiStrategy, atkState);
    if (ac < 1) { this._endTurn(); return; }
    const atkCommit = Math.min(ac, atkState.reserve);
    this._atkCommit = atkCommit;
    this._atkTentative = tentative;

    if (defState.reserve <= 0) {
      this._defManeuver = Maneuver.DEFENSELESS;
      this._defCommit = 0;
      this._defFollowup = 0;
      this._atkManeuver = chooseAtkManeuver(this._aiStrategy, atkState, atkCommit, 0, tentative);
      if (this._atkManeuver === Maneuver.FEINT) {
        // Defender will be treated as PARRY internally; pick follow-up vs PARRY.
        this._atkFollowup = chooseFollowup(this._aiStrategy, atkState.reserve - atkCommit, Maneuver.PARRY);
      } else {
        this._atkFollowup = 0;
      }
      this._resolveNow();
      return;
    }

    this.phase = Phase.AWAIT_DEF_COMMIT;
  }

  _resolveNow() {
    const atkIdx = this.attackerIdx;
    const defIdx = 1 - atkIdx;
    const atkState = this.states[atkIdx];
    const defState = this.states[defIdx];

    const preAtk = this._stateDict(atkState);
    const preDef = this._stateDict(defState);

    const result = resolveExchange({
      attacker: atkState,
      defender: defState,
      atkCommit: this._atkCommit,
      defCommit: this._defCommit,
      atkManeuver: this._atkManeuver,
      defManeuver: this._defManeuver,
      atkFollowupCommit: this._atkFollowup,
      defFollowupCommit: this._defFollowup,
      atkBonus: 0,
      atkEvasiveCommit: 0,
      defEvasiveCommit: 0,
      weaponBonus: this.settings.weapon_bonus,
      armorBonus: this.settings.armor_bonus,
      endTurnOnAttackerDamage: this.settings.end_turn_on_attacker_damage,
    });

    const postAtk = this._stateDict(atkState);
    const postDef = this._stateDict(defState);

    const entry = {
      kind: "exchange",
      turn: this.turn,
      exchange_in_turn: this.exchangeInTurn,
      attacker_idx: atkIdx,
      atk_maneuver: _maneuverLabel(this._atkManeuver),
      def_maneuver: _maneuverLabel(this._defManeuver),
      atk_commit: this._atkCommit,
      def_commit: this._defCommit,
      atk_followup: this._atkFollowup,
      def_followup: this._defFollowup,
      atk_rolled: result.atkRolled,
      atk_successes: result.atkSuccesses,
      def_rolled: result.defRolled,
      def_successes: result.defSuccesses,
      followup_rolled: result.followupRolled,
      followup_successes: result.followupSuccesses,
      dodge_rolled: result.dodgeRolled,
      dodge_successes: result.dodgeSuccesses,
      dodge_succeeded: result.dodgeSucceeded,
      damage_to_atk: result.attackerDamageTaken,
      damage_to_def: result.defenderDamageTaken,
      pre_atk: preAtk,
      pre_def: preDef,
      post_atk: postAtk,
      post_def: postDef,
    };
    this.lastExchange = entry;
    this._log(entry);

    if (atkState.totalHd <= 0) { this._enterGameOver(defIdx); return; }
    if (defState.totalHd <= 0) { this._enterGameOver(atkIdx); return; }

    if (this.settings.end_turn_on_attacker_damage && result.attackerDamageTaken > 0) {
      this._forceEndTurn = true;
    }

    if (atkIdx !== this.humanIdx) {
      this._aiContinueDecision = (!this._forceEndTurn && atkState.reserve >= 1)
        ? decideContinue(this._aiStrategy, result, atkState)
        : false;
    }

    this.phase = Phase.AWAIT_CONTINUE;
  }

  _endTurn() {
    if (this.turn >= 60) { this._enterGameOver(null); return; }
    this._log({ kind: "turn_end", turn: this.turn, attacker_idx: this.attackerIdx });
    this.attackerIdx = 1 - this.attackerIdx;
    this._beginTurn(false);
  }

  _enterGameOver(winnerIdx) {
    this.winnerIdx = winnerIdx;
    this.phase = Phase.GAME_OVER;
    this._log({ kind: "game_over", winner_idx: winnerIdx });
  }

  _currentPrompt() {
    const atkIdx = this.attackerIdx;
    const defIdx = 1 - atkIdx;

    if (this.phase === Phase.AWAIT_ATK_COMMIT) {
      return {
        kind: "atk_commit",
        for_idx: atkIdx,
        min: 1,
        max: this.states[atkIdx].reserve,
        can_end_turn: true,
      };
    }
    if (this.phase === Phase.AWAIT_DEF_COMMIT) {
      return {
        kind: "def_commit",
        for_idx: defIdx,
        min: 0,
        max: this.states[defIdx].reserve,
        atk_commit: this._atkCommit,
      };
    }
    if (this.phase === Phase.AWAIT_ATK_MANEUVER) {
      const reserveAfterCommit = this.states[atkIdx].reserve - this._atkCommit;
      const prompt = {
        kind: "atk_maneuver",
        for_idx: atkIdx,
        atk_commit: this._atkCommit,
        def_commit: this._defCommit,
        allowed: ["Attack", "Feint", "Dodge"],
        feint_followup_max: reserveAfterCommit,
        dodge_roll_max: reserveAfterCommit,
      };
      if (this.settings.exchange_mode === "sequential" && this._defManeuver !== null) {
        prompt.def_maneuver = _maneuverLabel(this._defManeuver);
      }
      return prompt;
    }
    if (this.phase === Phase.AWAIT_DEF_MANEUVER) {
      const reserveAfterCommit = this.states[defIdx].reserve - this._defCommit;
      return {
        kind: "def_maneuver",
        for_idx: defIdx,
        atk_commit: this._atkCommit,
        def_commit: this._defCommit,
        allowed: ["Parry", "Counter", "Dodge"],
        dodge_roll_max: reserveAfterCommit,
      };
    }
    if (this.phase === Phase.AWAIT_CONTINUE) {
      const humanIsAttacker = atkIdx === this.humanIdx;
      return {
        kind: "continue",
        human_decides: humanIsAttacker && !this._forceEndTurn,
        ai_decision: humanIsAttacker ? null : this._aiContinueDecision,
        attacker_can_continue: this.states[atkIdx].reserve >= 1,
        attacker_idx: atkIdx,
        force_end_turn: !!this._forceEndTurn,
      };
    }
    if (this.phase === Phase.GAME_OVER) {
      return { kind: "game_over" };
    }
    return { kind: "none" };
  }

  _log(entry) {
    this.log.push(entry);
  }
}
