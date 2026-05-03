"""Human-vs-AI combat session with a phase-driven state machine.

Single-user local app: exactly one GameSession lives in memory. Module-global
mutation of combat.WEAPON_BONUS / combat.ARMOR_BONUS is therefore safe; do not
run multiple GameSessions concurrently.
"""

import math
import random
from dataclasses import asdict
from enum import Enum

import combat
from combat import CombatantState, Maneuver, resolve_exchange
from strategy import Strategy, choose_attack, choose_defense, choose_followup, choose_dodge_roll, decide_continue
from settings_store import Settings


class Phase(str, Enum):
    IDLE = "idle"
    AWAIT_ATK_COMMIT = "await_atk_commit"
    AWAIT_DEF_COMMIT = "await_def_commit"
    AWAIT_ATK_MANEUVER = "await_atk_maneuver"
    AWAIT_DEF_MANEUVER = "await_def_maneuver"
    AWAIT_CONTINUE = "await_continue"
    GAME_OVER = "game_over"


_MANEUVER_NAMES = {
    Maneuver.SIMPLE_ATTACK: "Attack",
    Maneuver.FEINT: "Feint",
    Maneuver.DODGE: "Dodge",
    Maneuver.PARRY: "Parry",
    Maneuver.COUNTER: "Counter",
    Maneuver.DEFENSELESS: "Defenseless",
}


def _maneuver_label(m: Maneuver) -> str:
    return _MANEUVER_NAMES.get(m, m.value)


def _make_ai_strategy(difficulty: str) -> Strategy:
    s = Strategy()
    if difficulty == "easy":
        s.feint_prob = 0.10
        s.sa_commit_frac = 0.35
        s.dodge_prob_atk = 0.02
    elif difficulty == "hard":
        s.feint_prob = 0.55
        s.sa_commit_frac = 0.60
        s.dodge_prob_atk = 0.08
    # medium uses defaults
    return s.clip()


class GameSession:
    """Owns all state for an active bout. Drives the per-exchange state machine."""

    def __init__(self):
        self.phase: Phase = Phase.IDLE
        self.settings: Settings | None = None
        self.states: list[CombatantState] = []
        self.human_idx: int = 0
        self.attacker_idx: int = 0
        self.turn: int = 0
        self.exchange_in_turn: int = 0
        self.log: list[dict] = []
        self.last_exchange: dict | None = None
        self.winner_idx: int | None = None
        self._ai_strategy: Strategy | None = None

        # Per-exchange working state
        self._atk_commit: int = 0
        self._def_commit: int = 0
        self._atk_maneuver: Maneuver | None = None
        self._def_maneuver: Maneuver | None = None
        self._atk_followup: int = 0
        self._def_followup: int = 0

        # AI's continue decision when AI is attacker (stashed at end of resolve)
        self._ai_continue_decision: bool | None = None

    # ---- public API -------------------------------------------------------

    def new_game(self, settings: Settings) -> None:
        self.settings = settings
        self._ai_strategy = _make_ai_strategy(settings.ai_difficulty)
        hd = settings.combatant_dice
        self.states = [
            CombatantState(max_hd=hd, reserve=hd),
            CombatantState(max_hd=hd, reserve=hd),
        ]

        # Decide human / AI indices.
        if settings.human_role == "attacker":
            self.human_idx = 0
            initiative_winner = 0
        elif settings.human_role == "defender":
            self.human_idx = 0
            initiative_winner = 1
        else:  # random
            self.human_idx = random.randint(0, 1)
            initiative_winner = random.randint(0, 1)

        self.attacker_idx = initiative_winner
        loser_idx = 1 - initiative_winner
        loser = self.states[loser_idx]
        loser.reserve = math.ceil(loser.reserve * settings.initiative_loser_penalty)

        self.turn = 0
        self.exchange_in_turn = 0
        self.log = []
        self.last_exchange = None
        self.winner_idx = None
        self._reset_pending()
        self._ai_continue_decision = None

        self._log({
            "kind": "game_start",
            "human_idx": self.human_idx,
            "initiative_winner": initiative_winner,
            "settings": asdict(settings),
        })
        self._begin_turn(first=True)

    def submit_atk_commit(self, n: int | None = None, end_turn: bool = False) -> None:
        self._require_phase(Phase.AWAIT_ATK_COMMIT)
        self._require_human_is(self.attacker_idx)
        atk_state = self.states[self.attacker_idx]
        if end_turn:
            self._end_turn()
            return
        if n is None:
            raise ValueError("Must provide n or end_turn=True")
        if n < 1 or n > atk_state.reserve:
            raise ValueError(f"atk_commit must be in [1, {atk_state.reserve}]")
        self._atk_commit = n
        # AI is defender — choose its (maneuver, commit) now; reveal commit only.
        def_idx = 1 - self.attacker_idx
        dm, dc = choose_defense(self._ai_strategy, self.states[def_idx], n)
        self._def_maneuver = dm
        self._def_commit = min(dc, self.states[def_idx].reserve)
        if self._def_commit < 0:
            self._def_commit = 0
        self.phase = Phase.AWAIT_ATK_MANEUVER

    def submit_def_commit(self, n: int) -> None:
        self._require_phase(Phase.AWAIT_DEF_COMMIT)
        self._require_human_is(1 - self.attacker_idx)
        def_state = self.states[1 - self.attacker_idx]
        if n < 0 or n > def_state.reserve:
            raise ValueError(f"def_commit must be in [0, {def_state.reserve}]")
        self._def_commit = n
        self.phase = Phase.AWAIT_DEF_MANEUVER

    def submit_atk_maneuver(self, maneuver: str, followup: int | None = None, dodge_roll: int | None = None) -> None:
        self._require_phase(Phase.AWAIT_ATK_MANEUVER)
        self._require_human_is(self.attacker_idx)
        m = self._parse_atk_maneuver(maneuver)
        atk_state = self.states[self.attacker_idx]
        reserve_after_commit = atk_state.reserve - self._atk_commit

        atk_followup = 0
        if m == Maneuver.FEINT:
            atk_followup = max(0, min(reserve_after_commit, int(followup or 0)))
        elif m == Maneuver.DODGE:
            atk_followup = max(0, min(reserve_after_commit, int(dodge_roll or 0)))

        self._atk_maneuver = m
        self._atk_followup = atk_followup
        self._resolve_now()

    def submit_def_maneuver(self, maneuver: str, dodge_roll: int | None = None) -> None:
        self._require_phase(Phase.AWAIT_DEF_MANEUVER)
        self._require_human_is(1 - self.attacker_idx)
        m = self._parse_def_maneuver(maneuver)
        def_state = self.states[1 - self.attacker_idx]
        reserve_after_commit = def_state.reserve - self._def_commit

        def_followup = 0
        if m == Maneuver.DODGE:
            def_followup = max(0, min(reserve_after_commit, int(dodge_roll or 0)))

        self._def_maneuver = m
        self._def_followup = def_followup

        # AI is attacker; its maneuver was stashed at turn start. Compute its
        # follow-up now that it can see the defender's commit (via choose_followup
        # or choose_dodge_roll which reference the strategy's params).
        if self._atk_maneuver == Maneuver.FEINT:
            atk_state = self.states[self.attacker_idx]
            reserve_after_atk_commit = atk_state.reserve - self._atk_commit
            self._atk_followup = choose_followup(self._ai_strategy, reserve_after_atk_commit, m)
        elif self._atk_maneuver == Maneuver.DODGE:
            atk_state = self.states[self.attacker_idx]
            reserve_after_atk_commit = atk_state.reserve - self._atk_commit
            self._atk_followup = choose_dodge_roll(self._ai_strategy, reserve_after_atk_commit, "atk", m)
        else:
            self._atk_followup = 0

        self._resolve_now()

    def submit_continue(self, cont: bool | None = None) -> None:
        self._require_phase(Phase.AWAIT_CONTINUE)
        if self.winner_idx is not None:
            return  # already over

        if self.attacker_idx == self.human_idx:
            # Human attacker — they choose.
            if cont is None:
                raise ValueError("Must provide continue: bool")
            if cont and self.states[self.attacker_idx].reserve >= 1:
                self._begin_exchange()
            else:
                self._end_turn()
        else:
            # AI attacker — its decision is already stashed in _ai_continue_decision.
            if self._ai_continue_decision and self.states[self.attacker_idx].reserve >= 1:
                self._begin_exchange()
            else:
                self._end_turn()

    # ---- visible state ----------------------------------------------------

    def to_visible_dict(self) -> dict:
        if self.settings is None:
            return {"phase": Phase.IDLE.value}

        atk_idx = self.attacker_idx
        def_idx = 1 - atk_idx
        visible = {}

        # Show committed dice once a commit has been entered for the current exchange.
        # Hide AI maneuvers until reveal (post-resolve, in AWAIT_CONTINUE / GAME_OVER).
        if self.phase in (Phase.AWAIT_DEF_COMMIT, Phase.AWAIT_DEF_MANEUVER):
            # AI is attacker; expose its commit but never its maneuver here.
            visible["atk_commit"] = self._atk_commit
        if self.phase == Phase.AWAIT_ATK_MANEUVER:
            # AI is defender; expose its commit but never its maneuver here.
            visible["def_commit"] = self._def_commit

        prompt = self._current_prompt()

        return {
            "phase": self.phase.value,
            "turn": self.turn,
            "exchange_in_turn": self.exchange_in_turn,
            "human_idx": self.human_idx,
            "attacker_idx": atk_idx,
            "states": [self._state_dict(s) for s in self.states],
            "visible": visible,
            "prompt": prompt,
            "last_exchange": self.last_exchange,
            "log": self.log[-200:],  # cap to keep payloads small
            "winner_idx": self.winner_idx,
            "settings": asdict(self.settings),
        }

    # ---- internals --------------------------------------------------------

    def _state_dict(self, s: CombatantState) -> dict:
        return {
            "max_hd": s.max_hd,
            "reserve": s.reserve,
            "exchange": s.exchange,
            "used": s.used,
            "lost": s.lost,
            "total_hd": s.total_hd,
        }

    def _reset_pending(self) -> None:
        self._atk_commit = 0
        self._def_commit = 0
        self._atk_maneuver = None
        self._def_maneuver = None
        self._atk_followup = 0
        self._def_followup = 0

    def _require_phase(self, p: Phase) -> None:
        if self.phase != p:
            raise PermissionError(f"phase mismatch: expected {p.value}, current {self.phase.value}")

    def _require_human_is(self, idx: int) -> None:
        if self.human_idx != idx:
            raise PermissionError("not the human's turn for this action")

    def _parse_atk_maneuver(self, raw: str) -> Maneuver:
        m = (raw or "").lower()
        if m in ("attack", "simpleattack", "simple_attack", "sa"):
            return Maneuver.SIMPLE_ATTACK
        if m in ("feint", "f"):
            return Maneuver.FEINT
        if m in ("dodge", "d"):
            return Maneuver.DODGE
        raise ValueError(f"invalid attacker maneuver: {raw!r}")

    def _parse_def_maneuver(self, raw: str) -> Maneuver:
        m = (raw or "").lower()
        if m in ("parry", "p"):
            return Maneuver.PARRY
        if m in ("counter", "c"):
            return Maneuver.COUNTER
        if m in ("dodge", "d"):
            return Maneuver.DODGE
        raise ValueError(f"invalid defender maneuver: {raw!r}")

    def _begin_turn(self, first: bool = False) -> None:
        self.turn += 1
        self.exchange_in_turn = 0
        atk_idx = self.attacker_idx
        def_idx = 1 - atk_idx
        atk_state = self.states[atk_idx]
        def_state = self.states[def_idx]

        # Refresh per settings, mirroring strategy.run_combat lines 314-317.
        # On turn 1 the initiative penalty has already been applied; if
        # REFRESH_START_OF_TURN is True the attacker would refresh away the
        # penalty, but the penalty applies only to the *initiative loser* who
        # starts as the defender — so refreshing the new attacker is safe.
        if not first:
            if self.settings.refresh_start_of_turn:
                atk_state.refresh()
            if self.settings.refresh_end_of_turn:
                def_state.refresh()
        else:
            # First turn: the attacker is the initiative winner; they have full reserve.
            # No additional refresh needed regardless of flags.
            pass

        self._log({
            "kind": "turn_start",
            "turn": self.turn,
            "attacker_idx": atk_idx,
        })

        if atk_state.reserve < 1 and def_state.reserve < 1:
            # Stalemate this turn; nothing can happen. End turn to swap.
            if self.turn >= 60:
                self._enter_game_over(None)
                return
            self._end_turn()
            return

        self._begin_exchange()

    def _begin_exchange(self) -> None:
        self._reset_pending()
        self._ai_continue_decision = None
        self.exchange_in_turn += 1
        atk_idx = self.attacker_idx
        def_idx = 1 - atk_idx
        atk_state = self.states[atk_idx]
        def_state = self.states[def_idx]

        if atk_state.reserve < 1:
            # No dice to attack with — end turn.
            self._end_turn()
            return

        # Human attacker path
        if atk_idx == self.human_idx:
            # If defender is defenseless, we still ask the human for a commit (they
            # might want to commit minimally) and then auto-set DEFENSELESS later.
            self.phase = Phase.AWAIT_ATK_COMMIT
            return

        # AI attacker path: pick (maneuver, commit) now; reveal commit, hide maneuver.
        am, ac = choose_attack(self._ai_strategy, atk_state)
        if ac < 1:
            # AI declines to attack — end turn.
            self._end_turn()
            return
        ac = min(ac, atk_state.reserve)
        self._atk_maneuver = am
        self._atk_commit = ac

        # If defender (human) is defenseless, skip their phases entirely.
        if def_state.reserve <= 0:
            self._def_maneuver = Maneuver.DEFENSELESS
            self._def_commit = 0
            self._def_followup = 0
            # AI follow-up:
            if am == Maneuver.FEINT:
                # Defender will be converted to PARRY internally; choose follow-up vs PARRY.
                reserve_after_atk_commit = atk_state.reserve - ac
                self._atk_followup = choose_followup(self._ai_strategy, reserve_after_atk_commit, Maneuver.PARRY)
            elif am == Maneuver.DODGE:
                # AI dodging vs defenseless makes no sense; treat as no-op dodge roll = 0.
                self._atk_followup = 0
            else:
                self._atk_followup = 0
            self._resolve_now()
            return

        self.phase = Phase.AWAIT_DEF_COMMIT

    def _resolve_now(self) -> None:
        atk_idx = self.attacker_idx
        def_idx = 1 - atk_idx
        atk_state = self.states[atk_idx]
        def_state = self.states[def_idx]

        # Snapshot pre-state for the log entry.
        pre_atk = self._state_dict(atk_state)
        pre_def = self._state_dict(def_state)

        # Apply settings to the combat module before resolving.
        combat.WEAPON_BONUS = self.settings.weapon_bonus
        combat.ARMOR_BONUS = self.settings.armor_bonus

        result = resolve_exchange(
            atk_state, def_state,
            self._atk_commit, self._def_commit,
            self._atk_maneuver, self._def_maneuver,
            atk_followup_commit=self._atk_followup,
            def_followup_commit=self._def_followup,
            atk_bonus=0,
            atk_evasive_commit=0,
            def_evasive_commit=0,
        )

        post_atk = self._state_dict(atk_state)
        post_def = self._state_dict(def_state)

        entry = {
            "kind": "exchange",
            "turn": self.turn,
            "exchange_in_turn": self.exchange_in_turn,
            "attacker_idx": atk_idx,
            "atk_maneuver": _maneuver_label(self._atk_maneuver),
            "def_maneuver": _maneuver_label(self._def_maneuver),
            "atk_commit": self._atk_commit,
            "def_commit": self._def_commit,
            "atk_followup": self._atk_followup,
            "def_followup": self._def_followup,
            "atk_rolled": result.atk_rolled,
            "atk_successes": result.atk_successes,
            "def_rolled": result.def_rolled,
            "def_successes": result.def_successes,
            "followup_rolled": result.followup_rolled,
            "followup_successes": result.followup_successes,
            "dodge_rolled": result.dodge_rolled,
            "dodge_successes": result.dodge_successes,
            "dodge_succeeded": result.dodge_succeeded,
            "damage_to_atk": result.attacker_damage_taken,
            "damage_to_def": result.defender_damage_taken,
            "pre_atk": pre_atk,
            "pre_def": pre_def,
            "post_atk": post_atk,
            "post_def": post_def,
        }
        self.last_exchange = entry
        self._log(entry)

        # Check KO.
        if atk_state.total_hd <= 0:
            self._enter_game_over(def_idx)
            return
        if def_state.total_hd <= 0:
            self._enter_game_over(atk_idx)
            return

        # Pre-compute AI continue decision so the human only sees a "Next" prompt.
        if atk_idx != self.human_idx:
            if atk_state.reserve < 1:
                self._ai_continue_decision = False
            else:
                self._ai_continue_decision = decide_continue(self._ai_strategy, result, atk_state)

        self.phase = Phase.AWAIT_CONTINUE

    def _end_turn(self) -> None:
        if self.turn >= 60:
            # Stalemate cap (matches strategy.run_combat default max_turns spirit).
            self._enter_game_over(None)
            return
        self._log({
            "kind": "turn_end",
            "turn": self.turn,
            "attacker_idx": self.attacker_idx,
        })
        self.attacker_idx = 1 - self.attacker_idx
        self._begin_turn(first=False)

    def _enter_game_over(self, winner_idx: int | None) -> None:
        self.winner_idx = winner_idx
        self.phase = Phase.GAME_OVER
        self._log({"kind": "game_over", "winner_idx": winner_idx})

    def _current_prompt(self) -> dict:
        atk_idx = self.attacker_idx
        def_idx = 1 - atk_idx

        if self.phase == Phase.AWAIT_ATK_COMMIT:
            return {
                "kind": "atk_commit",
                "for_idx": atk_idx,
                "min": 1,
                "max": self.states[atk_idx].reserve,
                "can_end_turn": True,
            }
        if self.phase == Phase.AWAIT_DEF_COMMIT:
            return {
                "kind": "def_commit",
                "for_idx": def_idx,
                "min": 0,
                "max": self.states[def_idx].reserve,
                "atk_commit": self._atk_commit,
            }
        if self.phase == Phase.AWAIT_ATK_MANEUVER:
            atk_state = self.states[atk_idx]
            reserve_after_commit = atk_state.reserve - self._atk_commit
            return {
                "kind": "atk_maneuver",
                "for_idx": atk_idx,
                "atk_commit": self._atk_commit,
                "def_commit": self._def_commit,
                "allowed": ["Attack", "Feint", "Dodge"],
                "feint_followup_max": reserve_after_commit,
                "dodge_roll_max": reserve_after_commit,
            }
        if self.phase == Phase.AWAIT_DEF_MANEUVER:
            def_state = self.states[def_idx]
            reserve_after_commit = def_state.reserve - self._def_commit
            return {
                "kind": "def_maneuver",
                "for_idx": def_idx,
                "atk_commit": self._atk_commit,
                "def_commit": self._def_commit,
                "allowed": ["Parry", "Counter", "Dodge"],
                "dodge_roll_max": reserve_after_commit,
            }
        if self.phase == Phase.AWAIT_CONTINUE:
            human_is_attacker = (atk_idx == self.human_idx)
            atk_reserve = self.states[atk_idx].reserve
            return {
                "kind": "continue",
                "human_decides": human_is_attacker,
                "ai_decision": None if human_is_attacker else self._ai_continue_decision,
                "attacker_can_continue": atk_reserve >= 1,
                "attacker_idx": atk_idx,
            }
        if self.phase == Phase.GAME_OVER:
            return {"kind": "game_over"}
        return {"kind": "none"}

    def _log(self, entry: dict) -> None:
        self.log.append(entry)
