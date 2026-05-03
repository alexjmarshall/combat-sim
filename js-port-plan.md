# Port Web App to Client-Side JS, Host on Firebase

## Context

The Brigandine combat sim repo started as a Python genetic-algorithm sim (`evolve.py`, `combat.py`, `strategy.py`) for discovering dominant strategies in a custom RPG combat system. A Flask web app (`app.py`, `web_session.py`, `templates/`, `static/`) was added on top to let humans test the combat system interactively against AI strategies.

The user wants to share the web app with multiple users at once. The current Flask architecture cannot support this safely: `combat.py` mutates module-level globals (`WEAPON_BONUS`, `ARMOR_BONUS`) per session, so concurrent users on a single Flask process corrupt each other's combat math. Beyond that, the user prefers zero ongoing server costs/ops.

**Outcome:** Port only the web-app slice (web_session, the 5 strategy decision functions, combat resolution, settings) to client-side JavaScript hosted statically on Firebase Hosting. Each browser tab gets its own state automatically — multi-user concurrency is solved by construction. The Python GA pipeline (`evolve.py` + its dependencies on `combat.py` and `strategy.py`) stays untouched and continues to run locally.

**Hosting choice rationale:** Firebase Hosting was chosen over GitHub Pages because the user wants the source repo to stay private and wants a custom URL. GitHub Pages from a private repo requires a paid plan; Firebase serves only the deployed `docs/` artifacts, so the source remains private on whatever Git host. Free tier covers this comfortably (10 GB storage, 360 MB/day egress). Default URL is `<project>.web.app`; custom domain is a DNS verification step in the Firebase console.

## File Layout

Zero-tooling native ES modules. No bundler, no `node_modules`, no build step. Modern browsers run ES modules natively, and the ported surface is ~1000 lines of pure stdlib-equivalent logic with no runtime dependencies.

```
docs/                       (Firebase Hosting public directory)
  index.html                copy of templates/index.html, Jinja stripped, <script type="module" src="./app.js">
  style.css                 copy of static/style.css
  app.js                    UI + event handlers (adapted from static/app.js)
  rng.js                    rand(), randint(lo,hi), rollSuccesses(n) — single chokepoint over Math.random
  combat.js                 port of combat.py
  strategy.js               port of the 5 web-relevant fns from strategy.py
  session.js                port of web_session.py GameSession FSM
  settings.js               localStorage-backed equivalent of settings_store.py

firebase.json               { "hosting": { "public": "docs", "ignore": [...] } }
.firebaserc                 { "projects": { "default": "<chosen-firebase-project-id>" } }
```

## Module Contracts

- **`rng.js`** — exports `rand()`, `randint(lo, hi)`, `rollSuccesses(n)` (n d6, count >= 5). Single chokepoint so a seeded PRNG could be slotted in later without touching combat or strategy logic. v1 uses `Math.random()` only.

- **`combat.js`** — exports:
  - `Maneuver` (frozen object: `PARRY`, `COUNTER`, `SIMPLE_ATTACK`, `FEINT`, `DODGE`, `DECEPTIVE_ATTACK`, `DEFENSELESS`)
  - `CombatantState` class with `refresh()`, `commit()`, `clearExchangeToUsed()`, `applyDamageDefault()`, `totalHd` getter
  - `ExchangeResult` factory
  - `resolveExchange(opts)` — **`weaponBonus` and `armorBonus` are passed as fields on `opts`, never module globals.** This is the architectural change that fixes the multi-user bug.
  - Advanced-feature flags (`RIPOSTE`, `STOP_HIT`, `DECEPTIVE_ATTACK`, `EVASIVE_ATTACK`) likewise become `opts` fields, defaulting `false`.

- **`strategy.js`** — exports `Strategy` factory (returns plain object with `clip()`), `makeAiStrategy(difficulty)`, and the five porting targets: `chooseAttack`, `chooseDefense`, `chooseFollowup`, `chooseDodgeRoll`, `decideContinue`. GA-only functions (`mutate`, `crossover`, `runCombat` with stats) are NOT ported — they stay in Python `strategy.py`.

- **`session.js`** — exports `Phase` (frozen object) and `GameSession` mirroring `web_session.py` 1:1. Method names converted to camelCase: `newGame`, `submitAtkCommit`, `submitDefCommit`, `submitAtkManeuver`, `submitDefManeuver`, `submitContinue`, `toVisibleDict`. `_resolveNow` reads `weaponBonus`/`armorBonus` from `this.settings` and passes them into `resolveExchange()` as `opts` fields.

- **`settings.js`** — exports `defaultSettings()`, `loadSettings()`, `saveSettings(s)`, `settingsFromForm(payload)`. Backed by `localStorage` under key `bcs.settings.v1` (versioned prefix lets future schema changes coexist without migration). `settingsFromForm` mirrors `settings_store.settings_from_form` field-for-field so UI form code in `app.js` keeps working.

## How `static/app.js` Becomes `docs/app.js`

Keep churn minimal with a thin local "API" shim that mimics the old fetch surface, so existing `.then`/`await` chains stay structurally intact:

```js
import { GameSession } from "./session.js";
import { loadSettings, saveSettings, settingsFromForm } from "./settings.js";

const session = new GameSession();
const api = {
  getState: () => session.toVisibleDict(),
  newGame: () => {
    session.newGame(loadSettings());
    return session.toVisibleDict();
  },
  getSettings: () => loadSettings(),
  saveSettings: (form) => {
    const s = settingsFromForm(form);
    saveSettings(s);
    return s;
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
```

Each `fetch('/api/foo', {body: JSON.stringify(x)}).then(r => r.json())` becomes `Promise.resolve(api.foo(x))`. Wrapping in `Promise.resolve` preserves the async shape so `await` and `.then` chains don't need to change. Where the fetch code checked `response.ok`, replace with `try/catch` around the `api.*` call (validation errors thrown as `Error`).

## Verification (Manual Only)

Per user choice — no fixture harness, no automated tests. Verification process:

1. Run Flask app locally (`python app.py`) in one browser window, open `docs/index.html` via `python -m http.server 8000` (ES modules require `http://`, not `file://`) in another.
2. With identical settings on both sides, play 5+ full bouts side-by-side. Eyeball: turn counts, exchange counts, damage rolls, prompt text, log messages, win/loss outcomes look statistically similar. Note: RNG is unseeded, so exact roll-by-roll match is not expected — what's being checked is rule fidelity, not determinism.
3. Spot-check edge cases manually: low-HD combatants near death, dodge maneuvers, feint chains, counter-attacks, weapon/armor bonus extremes from settings.
4. Test settings persistence: change settings → reload page → settings preserved.
5. Test concurrency: open two tabs simultaneously, play in both, confirm no cross-talk.

## Phasing

Each phase leaves the system runnable. Flask app stays fully working until phase 7.

1. **Scaffold.** Create `docs/` with `index.html` (Jinja stripped), `style.css` (copy), `rng.js`, `settings.js`. Create `firebase.json` and `.firebaserc`. New files inert; Python app unchanged.
2. **Port `combat.js`.** Translate `combat.py` line-for-line. `weaponBonus`/`armorBonus` become `opts` fields, never globals. Smoke-test by importing in a scratch HTML page and calling `resolveExchange` from the console.
3. **Port `strategy.js`** — only `chooseAttack`, `chooseDefense`, `chooseFollowup`, `chooseDodgeRoll`, `decideContinue`. Same console smoke-test.
4. **Port `session.js`.** Translate `GameSession` 1:1 with camelCase. Console smoke-test the FSM by stepping through `submitAtkCommit` → `submitDefCommit` → … → `submitContinue`.
5. **Wire `docs/app.js`.** Copy `static/app.js`, add the imports + `api` shim, replace every `fetch('/api/...')` with the corresponding `Promise.resolve(api.*)` call. Serve via `python -m http.server` and play a full bout. Fix any visible-state shape deltas.
6. **Manual parity playthroughs** (per Verification section). Resolve discrepancies — almost always in `session.js` visible-state shaping or settings field coercion in `settings.js`.
7. **Deploy + delete Python web app** (single follow-up commit after verification passes):
   - `npm install -g firebase-tools` (one-time on dev machine).
   - `firebase login`, `firebase init hosting` → select project, public dir = `docs`, single-page = no, GitHub Action = no.
   - `firebase deploy --only hosting` → live at `<project>.web.app`.
   - (Optional) Configure custom domain in Firebase console under Hosting → Add custom domain.
   - In the SAME commit (or immediate follow-up), delete `app.py`, `web_session.py`, `templates/`, `static/`. Confirm `evolve.py`, `combat.py`, `strategy.py`, `settings_store.py` are not touched.

## Critical Files

**Read for porting (not modified):**

- [combat.py](c:\Users\Alex\Documents\code\brigandine-combat-sim\combat.py) — source of truth for `combat.js`
- [web_session.py](c:\Users\Alex\Documents\code\brigandine-combat-sim\web_session.py) — source of truth for `session.js`
- [strategy.py](c:\Users\Alex\Documents\code\brigandine-combat-sim\strategy.py) — source of truth for the 5 web-relevant functions in `strategy.js`
- [settings_store.py](c:\Users\Alex\Documents\code\brigandine-combat-sim\settings_store.py) — source of truth for `settings.js`
- [app.py](c:\Users\Alex\Documents\code\brigandine-combat-sim\app.py) — confirms the API surface the JS shim must expose
- [static/app.js](c:\Users\Alex\Documents\code\brigandine-combat-sim\static\app.js) — basis for `docs/app.js`
- [templates/index.html](c:\Users\Alex\Documents\code\brigandine-combat-sim\templates\index.html) — basis for `docs/index.html`
- [static/style.css](c:\Users\Alex\Documents\code\brigandine-combat-sim\static\style.css) — copied verbatim to `docs/style.css`

**Created:**

- `docs/index.html`, `docs/style.css`, `docs/app.js`, `docs/rng.js`, `docs/combat.js`, `docs/strategy.js`, `docs/session.js`, `docs/settings.js`
- `firebase.json`, `.firebaserc`

**Deleted in phase 7 (after verification):**

- `app.py`, `web_session.py`, `templates/`, `static/`

**Untouched throughout (guarantees `evolve.py` keeps working):**

- `combat.py`, `strategy.py`, `evolve.py`, `settings_store.py`

## Verification End-to-End

1. **Local dev:** `python -m http.server 8000` in `docs/`, navigate to `http://localhost:8000`, play full bouts.
2. **Concurrency test:** open two browser tabs, play simultaneously, confirm no state cross-talk.
3. **Settings persistence:** change settings, hard-reload, confirm preserved (localStorage).
4. **Side-by-side parity:** Flask on `:5000`, JS on `:8000`, identical settings, eyeball rule fidelity across 5+ bouts.
5. **Production deploy:** `firebase deploy --only hosting`, open `<project>.web.app` URL, repeat steps 2-3 against the live site.
6. **Custom domain (optional):** add via Firebase console, complete DNS TXT/A record verification, confirm HTTPS cert auto-provisions.
