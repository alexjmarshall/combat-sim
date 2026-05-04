// Brigandine Combat Playtester — frontend.

import { GameSession } from "./session.js";
import { loadSettings, saveSettings, settingsFromForm } from "./settings.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const session = new GameSession();

const api = {
  getSettings: () => loadSettings(),
  saveSettings: (form) => {
    const s = settingsFromForm(form);
    saveSettings(s);
    return s;
  },
  newGame: () => {
    session.newGame(loadSettings());
    return session.toVisibleDict();
  },
  atkCommit: (body) => {
    session.submitAtkCommit(body);
    return session.toVisibleDict();
  },
  defCommit: (body) => {
    session.submitDefCommit(body.n);
    return session.toVisibleDict();
  },
  atkManeuver: (body) => {
    session.submitAtkManeuver(body);
    return session.toVisibleDict();
  },
  defManeuver: (body) => {
    session.submitDefManeuver(body);
    return session.toVisibleDict();
  },
  continue: (body) => {
    session.submitContinue(body.continue);
    return session.toVisibleDict();
  },
};

let state = null;
let lastShownExchangeKey = null;

// ---------- Settings ----------

async function populateSettingsForm() {
  const s = api.getSettings();
  const form = $("#settings-form");
  form.weapon_bonus.value = s.weapon_bonus;
  form.armor_bonus.value = s.armor_bonus;
  form.combatant_dice.value = s.combatant_dice;
  form.initiative_loser_penalty.value = s.initiative_loser_penalty;
  form.refresh_start_of_turn.checked = s.refresh_start_of_turn;
  form.refresh_end_of_turn.checked = s.refresh_end_of_turn;
  form.human_role.value = s.human_role;
  form.ai_difficulty.value = s.ai_difficulty;
  form.exchange_mode.value = s.exchange_mode;
}

async function onSaveSettings(e) {
  e.preventDefault();
  const form = $("#settings-form");
  const payload = {
    weapon_bonus: form.weapon_bonus.value,
    armor_bonus: form.armor_bonus.value,
    combatant_dice: form.combatant_dice.value,
    initiative_loser_penalty: form.initiative_loser_penalty.value,
    refresh_start_of_turn: form.refresh_start_of_turn.checked,
    refresh_end_of_turn: form.refresh_end_of_turn.checked,
    human_role: form.human_role.value,
    ai_difficulty: form.ai_difficulty.value,
    exchange_mode: form.exchange_mode.value,
  };
  const statusEl = $("#settings-status");
  function settingsFlash(msg, isError = false) {
    statusEl.textContent = msg;
    statusEl.style.color = isError ? "#ef4444" : "";
    clearTimeout(statusEl._timer);
    statusEl._timer = setTimeout(() => {
      statusEl.textContent = "";
    }, 2000);
  }
  try {
    api.saveSettings(payload);
    settingsFlash("Settings saved.");
  } catch (err) {
    settingsFlash(`Could not save: ${err.message}`, true);
  }
}

function flash(msg, isError = false) {
  const el = $("#status-line");
  el.textContent = msg;
  if (isError) el.style.color = "#ef4444";
  else el.style.color = "";
}

// ---------- New game ----------

async function newGame() {
  $("#game-over-banner").classList.add("hidden");
  $("#reveal-panel").classList.add("hidden");
  lastShownExchangeKey = null;
  try {
    state = await Promise.resolve(api.newGame());
    $("#settings-overlay").classList.add("hidden");
    $("#game-panel").classList.remove("hidden");
    render();
  } catch (err) {
    flash(`Could not start: ${err.message}`, true);
  }
}

// ---------- Render ----------

function render() {
  if (!state || !state.states) return;
  renderCombatants();
  renderStatus();
  renderRevealIfNew();
  renderAction();
  renderLog();
  if (state.phase === "game_over") renderGameOver();
}

function renderCombatants() {
  const human = state.human_idx;
  const atk = state.attacker_idx;
  // Human always in slot 0 (left), opponent in slot 1 (right)
  const order = [human, 1 - human];
  for (let slot = 0; slot < 2; slot++) {
    const i = order[slot];
    const root = $(`#combatant-${slot}`);
    let s = state.states[i];
    // Attacker's committed dice don't move on the server until exchange resolution.
    // Reflect the pending commit visually during maneuver selection.
    if (
      (state.phase === "await_atk_maneuver" ||
        state.phase === "await_def_commit" ||
        state.phase === "await_def_maneuver") &&
      i === atk
    ) {
      const n = state.prompt.atk_commit;
      s = { ...s, reserve: s.reserve - n, exchange: s.exchange + n };
    }
    if (
      (state.phase === "await_atk_maneuver" ||
        state.phase === "await_def_maneuver") &&
      i !== atk
    ) {
      const n = state.prompt.def_commit;
      s = { ...s, reserve: s.reserve - n, exchange: s.exchange + n };
    }
    const isHuman = i === human;
    root.classList.toggle("is-human", isHuman);
    root.classList.toggle("is-ai", !isHuman);
    root.classList.toggle("is-attacker", i === atk);
    root.querySelector(".combatant-name").textContent = isHuman
      ? "You"
      : "Your Opponent";
    const role = i === atk ? "Attacker" : "Defender";
    const aiTag = !isHuman ? ` · AI (${state.settings.ai_difficulty})` : "";
    root.querySelector(".role-badge").textContent = `${role}${aiTag}`;
    renderHdBar(root.querySelector(".hd-segments"), s);
    root.querySelector(".hd-numbers").innerHTML = `
      <span class="num">Reserve <strong>${s.reserve}</strong></span>
      <span class="num">Spent <strong>${s.used}</strong></span>
      <span class="num">HD <strong>${s.total_hd}/${s.max_hd}</strong></span>
    `;
  }
}

function renderHdBar(container, s) {
  container.innerHTML = "";
  const total = Math.max(1, s.max_hd);
  const segs = [
    { cls: "reserve", n: s.reserve },
    { cls: "exchange", n: s.exchange },
    { cls: "used", n: s.used },
    { cls: "lost", n: s.lost },
  ];
  for (const { cls, n } of segs) {
    if (n <= 0) continue;
    const div = document.createElement("div");
    div.className = `seg ${cls}`;
    div.style.width = `${(n / total) * 100}%`;
    div.textContent = n > 0 ? n : "";
    container.appendChild(div);
  }
}

function renderStatus() {}

function renderAction() {
  const panel = $("#action-panel");
  panel.innerHTML = "";
  if (!state.prompt) return;
  const p = state.prompt;
  switch (p.kind) {
    case "atk_commit":
      renderAtkCommit(panel, p);
      break;
    case "def_commit":
      renderDefCommit(panel, p);
      break;
    case "atk_maneuver":
      renderAtkManeuver(panel, p);
      break;
    case "def_maneuver":
      renderDefManeuver(panel, p);
      break;
    case "continue":
      renderContinue(panel, p);
      break;
    case "game_over":
      panel.innerHTML = "<h3>Game over.</h3>";
      break;
    default:
      panel.innerHTML = "<p>Waiting…</p>";
  }
}

function previewAtkDice(n) {
  const s = state.states[state.attacker_idx];
  const preview = { ...s, reserve: s.reserve - n, exchange: s.exchange + n };
  const root = $("#combatant-0");
  renderHdBar(root.querySelector(".hd-segments"), preview);
  root.querySelector(".hd-numbers").innerHTML = `
    <span class="num">Reserve <strong>${preview.reserve}</strong></span>
    <span class="num">Spent <strong>${preview.used}</strong></span>
    <span class="num">HD <strong>${preview.total_hd}/${preview.max_hd}</strong></span>
  `;
}

function previewDefDice(n) {
  const s = state.states[1 - state.attacker_idx];
  const preview = { ...s, reserve: s.reserve - n, exchange: s.exchange + n };
  const root = $("#combatant-0");
  renderHdBar(root.querySelector(".hd-segments"), preview);
  root.querySelector(".hd-numbers").innerHTML = `
    <span class="num">Reserve <strong>${preview.reserve}</strong></span>
    <span class="num">Spent <strong>${preview.used}</strong></span>
    <span class="num">HD <strong>${preview.total_hd}/${preview.max_hd}</strong></span>
  `;
}

function renderAtkCommit(panel, p) {
  const defaultVal = Math.min(Math.ceil(p.max / 2), p.max);
  panel.innerHTML = `
    <h3>Commit dice to attack</h3>
    <p class="hint">You may commit between ${p.min} and ${p.max} dice.</p>
    <div class="row">
      <div class="commit-slider-wrap">
        <input type="range" id="commit-n" min="${p.min}" max="${p.max}" value="${defaultVal}">
        <span id="commit-n-val">${defaultVal}</span>
      </div>
      <button id="btn-commit">Commit</button>
      <button id="btn-end-turn" class="secondary">End Turn</button>
    </div>
  `;
  const slider = $("#commit-n");
  const valDisplay = $("#commit-n-val");
  slider.addEventListener("input", () => {
    const n = parseInt(slider.value, 10);
    valDisplay.textContent = n;
    previewAtkDice(n);
  });
  previewAtkDice(defaultVal);
  $("#btn-commit").addEventListener("click", async () => {
    await postAction(api.atkCommit, { n: parseInt(slider.value, 10) });
  });
  $("#btn-end-turn").addEventListener("click", async () => {
    await postAction(api.atkCommit, { end_turn: true });
  });
}

function renderDefCommit(panel, p) {
  const defaultVal = Math.min(p.atk_commit, p.max);
  panel.innerHTML = `
    <h3>Defender — commit dice</h3>
    <p>Your opponent committed <strong>${p.atk_commit}</strong> dice to their attack.</p>
    <p class="hint">You may commit between ${p.min} and ${p.max} dice.</p>
    <div class="row">
      <div class="commit-slider-wrap">
        <input type="range" id="commit-n" min="${p.min}" max="${p.max}" value="${defaultVal}">
        <span id="commit-n-val">${defaultVal}</span>
      </div>
      <button id="btn-commit">Commit</button>
    </div>
  `;
  const slider = $("#commit-n");
  const valDisplay = $("#commit-n-val");
  slider.addEventListener("input", () => {
    const n = parseInt(slider.value, 10);
    valDisplay.textContent = n;
    previewDefDice(n);
  });
  previewDefDice(defaultVal);
  $("#btn-commit").addEventListener("click", async () => {
    await postAction(api.defCommit, { n: parseInt(slider.value, 10) });
  });
}

function renderAtkManeuver(panel, p) {
  const feintMax = p.feint_followup_max;
  const dodgeMax = p.dodge_roll_max;
  const defLine = p.def_maneuver
    ? `You committed <strong>${p.atk_commit}</strong> dice. Your opponent committed <strong>${p.def_commit}</strong> dice and declared <strong>${p.def_maneuver}</strong>.`
    : `You committed <strong>${p.atk_commit}</strong> dice. Your opponent committed <strong>${p.def_commit}</strong> dice.`;
  panel.innerHTML = `
    <h3>Choose your attacker maneuver</h3>
    <p>${defLine}</p>
    <div class="maneuver-grid">
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Attack">Attack</button>
      </div>
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Feint">Feint</button>
        <label class="param-label">Follow-up (max ${feintMax})
          <input type="number" id="feint-followup" min="0" max="${feintMax}" value="${feintMax}">
        </label>
      </div>
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Dodge">Dodge</button>
        <label class="param-label">Dodge-roll (max ${dodgeMax})
          <input type="number" id="dodge-roll-atk" min="0" max="${dodgeMax}" value="${Math.min(4, dodgeMax)}">
        </label>
      </div>
    </div>
  `;
  $$("#action-panel .maneuver-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const m = btn.dataset.m;
      const body = { maneuver: m };
      if (m === "Feint")
        body.followup = parseInt($("#feint-followup").value, 10) || 0;
      if (m === "Dodge")
        body.dodge_roll = parseInt($("#dodge-roll-atk").value, 10) || 0;
      await postAction(api.atkManeuver, body);
    });
  });
}

function renderDefManeuver(panel, p) {
  const dodgeMax = p.dodge_roll_max;
  panel.innerHTML = `
    <h3>Choose your defender maneuver</h3>
    <p>Your opponent committed <strong>${p.atk_commit}</strong> dice. You committed <strong>${p.def_commit}</strong> dice.</p>
    <div class="maneuver-grid">
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Parry">Parry</button>
      </div>
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Counter">Counter</button>
      </div>
      <div class="maneuver-option">
        <button class="maneuver-btn" data-m="Dodge">Dodge</button>
        <label class="param-label">Dodge-roll (max ${dodgeMax})
          <input type="number" id="dodge-roll-def" min="0" max="${dodgeMax}" value="${Math.min(4, dodgeMax)}">
        </label>
      </div>
    </div>
  `;
  $$("#action-panel .maneuver-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const m = btn.dataset.m;
      const body = { maneuver: m };
      if (m === "Dodge")
        body.dodge_roll = parseInt($("#dodge-roll-def").value, 10) || 0;
      await postAction(api.defManeuver, body);
    });
  });
}

function renderContinue(panel, p) {
  if (p.human_decides) {
    if (!p.attacker_can_continue) {
      panel.innerHTML = `
        <h3>Out of dice — turn ends</h3>
        <p>You have no reserve left. Click Next to pass to the Opponent.</p>
        <div class="row">
          <button id="btn-next">Next</button>
        </div>
      `;
      $("#btn-next").addEventListener("click", async () => {
        await postAction(api["continue"], { continue: false });
      });
    } else {
      panel.innerHTML = `
        <h3>Continue Attacking?</h3>
        <p>You may keep attacking while you have dice in reserve.</p>
        <div class="row">
          <button id="btn-continue">Continue</button>
          <button id="btn-end" class="secondary">End Turn</button>
        </div>
      `;
      $("#btn-continue").addEventListener("click", async () => {
        await postAction(api["continue"], { continue: true });
      });
      $("#btn-end").addEventListener("click", async () => {
        await postAction(api["continue"], { continue: false });
      });
    }
  } else {
    const willContinue = p.ai_decision && p.attacker_can_continue;
    const msg = willContinue
      ? "Your opponent will continue attacking."
      : "Your opponent ends their turn.";
    panel.innerHTML = `
      <h3>${msg}</h3>
      <div class="row">
        <button id="btn-next">Next</button>
      </div>
    `;
    $("#btn-next").addEventListener("click", async () => {
      await postAction(api["continue"], {});
    });
  }
}

function renderRevealIfNew() {
  const lx = state.last_exchange;
  const reveal = $("#reveal-panel");
  const pk = state.prompt ? state.prompt.kind : null;
  if (!lx || (pk !== "continue" && pk !== "game_over")) {
    reveal.classList.add("hidden");
    return;
  }
  const key = `${lx.turn}:${lx.exchange_in_turn}`;
  reveal.classList.remove("hidden");
  reveal.innerHTML = renderRevealHTML(lx);
  lastShownExchangeKey = key;
}

function renderRevealHTML(x) {
  const human = state.human_idx;
  const youAreAtk = x.attacker_idx === human;

  const you = youAreAtk ? "you" : "your opponent";
  const opp = youAreAtk ? "your opponent" : "you";
  const You = youAreAtk ? "You" : "Your opponent";
  const Opp = youAreAtk ? "Your opponent" : "You";
  const your = youAreAtk ? "your" : "your opponent's";
  const oppY = youAreAtk ? "your opponent's" : "your";

  const fuD = x.atk_followup;
  const dodR = x.dodge_rolled;
  const dodOK = x.dodge_succeeded;
  const dmgDef = x.damage_to_def;
  const dmgAtk = x.damage_to_atk;

  function hits(n) {
    return n === 1 ? "1 hit" : `${n} hits`;
  }
  // Conjugate verb for attacker subject (2nd person when youAreAtk, else 3rd)
  function av(base, irr) {
    return youAreAtk ? base : irr || base + "s";
  }
  // Conjugate verb for defender subject (3rd person when youAreAtk, else 2nd)
  function dv(base, irr) {
    return youAreAtk ? irr || base + "s" : base;
  }

  const am = x.atk_maneuver;
  const dm = x.def_maneuver;

  const W = state.settings.weapon_bonus;
  const A = state.settings.armor_bonus;
  function rawDmg(h, capDice) {
    return Math.max(0, h + Math.min(W, capDice) - A);
  }
  function woundLabel(raw) {
    if (raw >= 3) return "Grievous Wound";
    if (raw === 2) return "Serious Wound";
    return null;
  }

  let rawToDef = 0,
    rawToAtk = 0;
  if (am === "Attack" && dm === "Parry") {
    const net = x.atk_successes - x.def_successes;
    if (net >= 1) rawToDef = rawDmg(net, x.atk_rolled);
  } else if (am === "Attack" && dm === "Counter") {
    if (x.atk_successes >= 1) rawToDef = rawDmg(x.atk_successes, x.atk_rolled);
    if (x.def_successes >= 1) rawToAtk = rawDmg(x.def_successes, x.def_rolled);
  } else if (am === "Attack" && dm === "Dodge") {
    if (!dodOK && x.atk_successes >= 1)
      rawToDef = rawDmg(x.atk_successes, x.atk_rolled);
  } else if (am === "Feint" && dm === "Parry") {
    if (x.followup_successes >= 1)
      rawToDef = rawDmg(x.followup_successes, x.followup_rolled);
  } else if (am === "Feint" && dm === "Counter") {
    if (x.def_successes >= 1) rawToAtk = rawDmg(x.def_successes, x.def_rolled);
    if (x.followup_successes >= 1)
      rawToDef = rawDmg(x.followup_successes, x.followup_rolled);
  } else if (am === "Dodge" && dm === "Counter") {
    if (!dodOK && x.def_successes >= 1)
      rawToAtk = rawDmg(x.def_successes, x.def_rolled);
  } else if (am === "Feint" && dm === "Dodge") {
    if (!dodOK && x.followup_successes >= 1)
      rawToDef = rawDmg(x.followup_successes, x.followup_rolled);
  } else if (dm === "Defenseless") {
    if (am === "Feint" && x.followup_rolled > 0 && x.followup_successes >= 1)
      rawToDef = rawDmg(x.followup_successes, x.followup_rolled);
    else if (x.atk_successes >= 1)
      rawToDef = rawDmg(x.atk_successes, x.atk_rolled);
  }

  const rawPlayerDealt = youAreAtk ? rawToDef : rawToAtk;
  const rawPlayerTook = youAreAtk ? rawToAtk : rawToDef;
  const dealtLabel = woundLabel(rawPlayerDealt);
  const tookLabel = woundLabel(rawPlayerTook);
  function dmgStr(hd, label) {
    return label ? `a ${label}` : `${hd} damage`;
  }

  const paras = [];

  if (am === "Attack" && dm === "Parry") {
    paras.push(
      `${You} ${av("press", "presses")} the attack. ${Opp} ${dv("stand")} firm and ${dv("parry", "parries")}.`,
    );
    if (dmgDef > 0)
      paras.push(`${youAreAtk ? "Your" : "Their"} blow breaks through.`);
    else paras.push(`The parry holds.`);
  } else if (am === "Attack" && dm === "Counter") {
    paras.push(
      `${You} ${av("drive")} in. ${Opp} ${dv("meet", "meets")} it with a counter.`,
    );
  } else if (am === "Attack" && dm === "Dodge") {
    paras.push(
      `${You} ${av("press", "presses")} forward. ${Opp} ${dv("try", "tries")} to get clear.`,
    );
    if (dodOK)
      paras.push(`${Opp} ${dv("slip", "slips")} outside ${your} reach.`);
    else paras.push(`The dodge falls short.`);
  } else if (am === "Feint" && dm === "Parry") {
    paras.push(
      `${You} ${av("feint", "feints")}, drawing ${oppY} guard wide. ${Opp} ${dv("commit", "commits")} to a parry.`,
    );
    if (fuD > 0)
      paras.push(`${You} ${av("make", "makes")} a follow-up attack.`);
    else
      paras.push(
        `${You} ${av("leave", "leaves")} no follow-up — the feint ends without a real thrust.`,
      );
  } else if (am === "Feint" && dm === "Counter") {
    paras.push(
      `${You} ${av("feint", "feints")}, trying to bait a response. ${Opp} ${dv("counter-attack", "counter-attacks")} immediately instead.`,
    );
    if (fuD === 0) paras.push(`With no follow-up, ${your} feint buys nothing.`);
  } else if (am === "Feint" && dm === "Dodge") {
    paras.push(
      `${You} ${av("feint", "feints")}, setting up a follow-through. ${Opp} ${dv("don't", "doesn't")} wait and ${dv("try", "tries")} to clear the distance.`,
    );
    if (dodOK) paras.push(`${Opp} ${dv("clear", "clears")} the angle in time.`);
    else if (fuD > 0)
      paras.push(
        `The dodge misfires — ${you} ${av("make", "makes")} a follow-up attack.`,
      );
    else
      paras.push(
        `The dodge misfires, but ${you} ${av("have", "has")} no follow-up to exploit it.`,
      );
  } else if (am === "Dodge" && dm === "Parry") {
    paras.push(
      `${You} ${av("break")} off. ${Opp} ${dv("brace", "braces")} for a blow that never comes.`,
    );
    if (dodR > 0) {
      if (dodOK) paras.push(`${You} ${av("disengage", "disengages")} cleanly.`);
      else
        paras.push(`${youAreAtk ? "Your" : "Their"} withdrawal is too slow.`);
    }
  } else if (am === "Dodge" && dm === "Counter") {
    paras.push(
      `${You} ${av("try", "tries")} to disengage. ${Opp} ${dv("read", "reads")} the opening and ${dv("counter", "counters")}.`,
    );
    if (dodR > 0) {
      if (dodOK)
        paras.push(
          `${You} ${av("slip", "slips")} away before the counter connects.`,
        );
      else
        paras.push(
          `${youAreAtk ? "Their" : "Your"} counter finds ${you} mid-retreat.`,
        );
    }
  } else if (am === "Dodge" && dm === "Dodge") {
    paras.push(`Both combatants break away at the same moment.`);
    paras.push(`The exchange dissolves without a blow struck.`);
  } else if (dm === "Defenseless") {
    paras.push(
      youAreAtk
        ? `You attack a defenseless opponent.`
        : `Your opponent attacks you while you're defenseless.`,
    );
  } else {
    paras.push(`${You} ${av("use", "uses")} ${am} against ${oppY} ${dm}.`);
  }

  // Always end with an explicit hit/miss result from the player's perspective
  const playerDealt = youAreAtk ? dmgDef : dmgAtk;
  const playerTook = youAreAtk ? dmgAtk : dmgDef;
  if (playerDealt > 0 && playerTook > 0)
    paras.push(
      `You deal ${dmgStr(playerDealt, dealtLabel)} and take ${dmgStr(playerTook, tookLabel)}.`,
    );
  else if (playerDealt > 0)
    paras.push(`You deal ${dmgStr(playerDealt, dealtLabel)}.`);
  else if (playerTook > 0)
    paras.push(`You take ${dmgStr(playerTook, tookLabel)}.`);
  else paras.push(`No damage.`);

  const atkShort = youAreAtk ? "You" : "Opp";
  const defShort = youAreAtk ? "Opp" : "You";

  const mechLines = [];
  if (x.atk_rolled > 0) {
    mechLines.push(
      `${atkShort}: ${x.atk_maneuver} · ${x.atk_commit} committed · ${x.atk_successes}/${x.atk_rolled} successes`,
    );
  } else {
    mechLines.push(
      `${atkShort}: ${x.atk_maneuver} · ${x.atk_commit} committed · (no roll)`,
    );
  }
  if (x.def_rolled > 0) {
    if (dm === "Parry" && am === "Attack") {
      const rawDef = Math.floor(x.def_successes / 2);
      mechLines.push(
        `${defShort}: ${x.def_maneuver} · ${x.def_commit} committed · ${rawDef}/${x.def_rolled} successes (×2 = ${x.def_successes} effective)`,
      );
    } else {
      mechLines.push(
        `${defShort}: ${x.def_maneuver} · ${x.def_commit} committed · ${x.def_successes}/${x.def_rolled} successes`,
      );
    }
  } else {
    mechLines.push(
      `${defShort}: ${x.def_maneuver} · ${x.def_commit} committed`,
    );
  }
  if (x.followup_rolled > 0) {
    mechLines.push(
      `Follow-up: ${x.followup_successes}/${x.followup_rolled} successes`,
    );
  }
  if (x.dodge_rolled > 0) {
    mechLines.push(
      `Dodge: ${x.dodge_successes}/${x.dodge_rolled} — ${x.dodge_succeeded ? "passed" : "failed"}`,
    );
  }

  function fmtDmg(label, hits, capDice) {
    const effWep = Math.min(W, capDice);
    const wepStr = effWep < W ? `min(${W},${capDice}d)` : `${effWep}`;
    const raw = Math.max(0, hits + effWep - A);
    let suffix = "";
    if (raw >= 3) suffix = ` → Grievous Wound (×3 = ${raw * 3} HD)`;
    else if (raw === 2) suffix = ` → Serious Wound (×2 = 4 HD)`;
    return `${label}: ${hits} hit${hits !== 1 ? "s" : ""} + ${wepStr} wep − ${A} arm = ${raw}${suffix}`;
  }

  const formulaLines = [];
  if (am === "Attack" && dm === "Parry") {
    const net = x.atk_successes - x.def_successes;
    if (net >= 1) formulaLines.push(fmtDmg(atkShort, net, x.atk_rolled));
  } else if (am === "Attack" && dm === "Counter") {
    if (x.atk_successes >= 1)
      formulaLines.push(fmtDmg(atkShort, x.atk_successes, x.atk_rolled));
    if (x.def_rolled > 0 && x.def_successes >= 1)
      formulaLines.push(fmtDmg(defShort, x.def_successes, x.def_rolled));
  } else if (am === "Attack" && dm === "Dodge") {
    if (!dodOK && x.atk_successes >= 1)
      formulaLines.push(fmtDmg(atkShort, x.atk_successes, x.atk_rolled));
  } else if (am === "Feint" && dm === "Parry") {
    if (x.followup_rolled > 0 && x.followup_successes >= 1)
      formulaLines.push(
        fmtDmg(atkShort, x.followup_successes, x.followup_rolled),
      );
  } else if (am === "Feint" && dm === "Counter") {
    if (x.def_successes >= 1)
      formulaLines.push(fmtDmg(defShort, x.def_successes, x.def_rolled));
    if (x.followup_rolled > 0 && x.followup_successes >= 1)
      formulaLines.push(
        fmtDmg(atkShort, x.followup_successes, x.followup_rolled),
      );
  } else if (am === "Dodge" && dm === "Counter") {
    if (!dodOK && x.def_successes >= 1)
      formulaLines.push(fmtDmg(defShort, x.def_successes, x.def_rolled));
  } else if (am === "Feint" && dm === "Dodge") {
    if (!dodOK && x.followup_successes >= 1)
      formulaLines.push(
        fmtDmg(atkShort, x.followup_successes, x.followup_rolled),
      );
  } else if (dm === "Defenseless") {
    if (am === "Feint" && x.followup_rolled > 0 && x.followup_successes >= 1)
      formulaLines.push(
        fmtDmg(atkShort, x.followup_successes, x.followup_rolled),
      );
    else if (x.atk_successes >= 1)
      formulaLines.push(fmtDmg(atkShort, x.atk_successes, x.atk_rolled));
  }

  return `
    <div class="narrative-body">
      ${paras.map((p) => `<p>${p}</p>`).join("")}
      <div class="narrative-outcome">
        ${mechLines.map((l) => `<div class="mech-line">${l}</div>`).join("")}
        ${formulaLines.map((l) => `<div class="mech-line formula-line">${l}</div>`).join("")}
      </div>
    </div>
  `;
}

function renderLog() {
  const root = $("#log");
  root.innerHTML = state.log.map(formatLogEntry).join("");
  root.scrollTop = root.scrollHeight;
}

function formatLogEntry(e) {
  if (e.kind === "game_start") {
    const role = e.human_idx === e.initiative_winner ? "you" : "Opponent";
    return `<div class="log-entry game-start">Game start. Initiative: ${role} go first.</div>`;
  }
  if (e.kind === "turn_start") {
    const who = e.attacker_idx === state.human_idx ? "Your" : "Opponent's";
    return `<div class="log-entry turn-start">— Turn ${e.turn}: ${who} attacking turn —</div>`;
  }
  if (e.kind === "turn_end") {
    return `<div class="log-entry turn-end">— Turn ${e.turn} ends —</div>`;
  }
  if (e.kind === "game_over") {
    if (e.winner_idx === null)
      return `<div class="log-entry game-over">Stalemate.</div>`;
    const who =
      e.winner_idx === state.human_idx ? "You win!" : "Opponent wins.";
    return `<div class="log-entry game-over">${who}</div>`;
  }
  if (e.kind === "exchange") {
    const youAtk = e.attacker_idx === state.human_idx;
    const atkL = youAtk ? "You" : "Opp";
    const defL = youAtk ? "Opp" : "You";
    let s = `<div class="log-entry">`;
    s += `T${e.turn}.${e.exchange_in_turn}: `;
    s += `${atkL} ${e.atk_maneuver}(${e.atk_commit})`;
    if (e.atk_followup) s += `+${e.atk_followup}`;
    s += ` vs ${defL} ${e.def_maneuver}(${e.def_commit})`;
    if (e.def_followup) s += `+${e.def_followup}`;
    if (e.atk_rolled || e.def_rolled || e.followup_rolled || e.dodge_rolled) {
      const rolls = [];
      if (e.atk_rolled) rolls.push(`atk ${e.atk_successes}/${e.atk_rolled}`);
      if (e.def_rolled) rolls.push(`def ${e.def_successes}/${e.def_rolled}`);
      if (e.followup_rolled)
        rolls.push(`fu ${e.followup_successes}/${e.followup_rolled}`);
      if (e.dodge_rolled)
        rolls.push(
          `dodge ${e.dodge_successes}/${e.dodge_rolled}${e.dodge_succeeded ? "✓" : "✗"}`,
        );
      s += ` [${rolls.join(", ")}]`;
    }
    if (e.damage_to_def > 0) s += ` → ${defL} -${e.damage_to_def}`;
    if (e.damage_to_atk > 0) s += ` → ${atkL} -${e.damage_to_atk}`;
    if (e.damage_to_atk === 0 && e.damage_to_def === 0) s += ` → no damage`;
    s += `</div>`;
    return s;
  }
  return "";
}

function renderGameOver() {
  const banner = $("#game-over-banner");
  let msg;
  if (state.winner_idx === null) msg = "Stalemate.";
  else if (state.winner_idx === state.human_idx) msg = "You win!";
  else msg = "Your opponent wins.";
  banner.innerHTML = `
    <div>${msg}</div>
    <button id="btn-rematch">Rematch</button>
  `;
  banner.classList.remove("hidden");
  $("#btn-rematch").addEventListener("click", () => newGame());
}

// ---------- Action helpers ----------

async function postAction(apiCall, body) {
  try {
    state = await Promise.resolve(apiCall(body));
    render();
  } catch (err) {
    flash(`Error: ${err.message}`, true);
  }
}

// ---------- Wire up ----------

document.addEventListener("DOMContentLoaded", async () => {
  await populateSettingsForm();
  $("#settings-form").addEventListener("submit", onSaveSettings);
  $("#new-game").addEventListener("click", newGame);
  $("#toggle-settings").addEventListener("click", () => {
    const overlay = $("#settings-overlay");
    const nowHidden = overlay.classList.toggle("hidden");
    if (!nowHidden) populateSettingsForm();
  });
  $("#close-settings").addEventListener("click", () => {
    $("#settings-overlay").classList.add("hidden");
  });
  $("#settings-overlay").addEventListener("click", (e) => {
    if (e.target === $("#settings-overlay"))
      $("#settings-overlay").classList.add("hidden");
  });
  await newGame();
});
