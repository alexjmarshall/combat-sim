const STORAGE_KEY = "bcs.settings.v1";

export function defaultSettings() {
  return {
    weapon_bonus: 2,
    armor_bonus: 2,
    refresh_start_of_turn: true,
    refresh_end_of_turn: false,
    combatant_dice: 10,
    initiative_loser_penalty: 0.5,
    human_role: "random",
    ai_difficulty: "medium",
    exchange_mode: "simultaneous",
    end_turn_on_attacker_damage: true,
  };
}

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultSettings();
    const data = JSON.parse(raw);
    const defaults = defaultSettings();
    const out = {};
    for (const k of Object.keys(defaults)) {
      out[k] = k in data ? data[k] : defaults[k];
    }
    return out;
  } catch {
    return defaultSettings();
  }
}

export function saveSettings(s) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

export function settingsFromForm(form) {
  function toBool(v) {
    if (typeof v === "boolean") return v;
    return ["true", "1", "yes", "on"].includes(String(v).toLowerCase());
  }

  const s = {
    weapon_bonus: Math.max(0, parseInt(form.weapon_bonus ?? 2, 10)),
    armor_bonus: Math.max(0, parseInt(form.armor_bonus ?? 2, 10)),
    refresh_start_of_turn: toBool(form.refresh_start_of_turn ?? true),
    refresh_end_of_turn: toBool(form.refresh_end_of_turn ?? false),
    combatant_dice: Math.max(1, parseInt(form.combatant_dice ?? 10, 10)),
    initiative_loser_penalty: Math.max(0, Math.min(1, parseFloat(form.initiative_loser_penalty ?? 0.5))),
    human_role: form.human_role ?? "random",
    ai_difficulty: form.ai_difficulty ?? "medium",
    exchange_mode: form.exchange_mode ?? "simultaneous",
  };

  if (!["attacker", "defender", "random"].includes(s.human_role)) s.human_role = "random";
  if (!["easy", "medium", "hard"].includes(s.ai_difficulty)) s.ai_difficulty = "medium";
  if (!["simultaneous", "sequential"].includes(s.exchange_mode)) s.exchange_mode = "simultaneous";
  s.end_turn_on_attacker_damage = toBool(form.end_turn_on_attacker_damage ?? true);

  return s;
}
