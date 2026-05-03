"""Persistent settings for the web playtester."""

import json
import os
from dataclasses import dataclass, asdict, fields

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


@dataclass
class Settings:
    weapon_bonus: int = 2
    armor_bonus: int = 2
    refresh_start_of_turn: bool = True
    refresh_end_of_turn: bool = False
    combatant_dice: int = 10
    initiative_loser_penalty: float = 0.5
    human_role: str = "random"  # "attacker" | "defender" | "random"
    ai_difficulty: str = "medium"  # "easy" | "medium" | "hard"


def load_settings() -> Settings:
    if not os.path.exists(SETTINGS_PATH):
        return Settings()
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        valid = {f.name for f in fields(Settings)}
        return Settings(**{k: v for k, v in data.items() if k in valid})
    except (json.JSONDecodeError, TypeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    with open(SETTINGS_PATH, "w") as f:
        json.dump(asdict(settings), f, indent=2)


def settings_from_form(form: dict) -> Settings:
    """Coerce a dict (e.g., from request JSON) into a validated Settings."""
    def to_bool(v):
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("true", "1", "yes", "on")

    s = Settings(
        weapon_bonus=max(0, int(form.get("weapon_bonus", 2))),
        armor_bonus=max(0, int(form.get("armor_bonus", 2))),
        refresh_start_of_turn=to_bool(form.get("refresh_start_of_turn", True)),
        refresh_end_of_turn=to_bool(form.get("refresh_end_of_turn", False)),
        combatant_dice=max(1, int(form.get("combatant_dice", 10))),
        initiative_loser_penalty=max(0.0, min(1.0, float(form.get("initiative_loser_penalty", 0.5)))),
        human_role=form.get("human_role", "random"),
        ai_difficulty=form.get("ai_difficulty", "medium"),
    )
    if s.human_role not in ("attacker", "defender", "random"):
        s.human_role = "random"
    if s.ai_difficulty not in ("easy", "medium", "hard"):
        s.ai_difficulty = "medium"
    return s
