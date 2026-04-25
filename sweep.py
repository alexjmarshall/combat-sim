"""Sweep evolve() across parameter combinations and flag diversity concerns."""

import random
from collections import defaultdict

import combat
import strategy as strat_module
from evolve import evolve

DICE_VALUES = [4, 6, 9, 13, 18]
BONUS_COMBOS = [(2, 1), (3, 1), (2, 2), (1, 2)]  # (weapon_bonus, armor_bonus)
MANEUVER_MODES = [False, True]

EVOLVE_KWARGS = dict(pop_size=60, gens=40, games=3, opps_n=10, mut=0.06, elite=0.1, verbose=False)

DP_THRESHOLD = 0.99   # flag if top strategy's dodge/counter prob hits the clip ceiling
MARGINAL_THRESHOLD = 5.0  # flag if any enabled maneuver appears in < 5% of exchanges


def patch_globals(weapon_bonus, armor_bonus, advanced):
    combat.WEAPON_BONUS = weapon_bonus
    combat.ARMOR_BONUS = armor_bonus
    combat.RIPOSTE = advanced
    combat.STOP_HIT = advanced
    combat.DECEPTIVE_ATTACK = advanced
    combat.EVASIVE_ATTACK = advanced
    # strategy.py imported DECEPTIVE_ATTACK by value, so patch its local name too
    strat_module.DECEPTIVE_ATTACK_ENABLED = advanced


def compute_marginals(finals):
    """Aggregate maneuver frequencies across top 10 strategies, mirroring report()."""
    totals = defaultdict(int)
    te = 0
    for s, wr, mc, tc, commits, turns, hit_damages, bout_max_damages in finals[:10]:
        te += tc
        for k, v in mc.items():
            totals[k] += v

    tm = max(1, te)
    sa_t  = totals['SA_vs_P'] + totals['SA_vs_C'] + totals['SA_vs_D'] + totals['SA_vs_X']
    f_t   = totals['F_vs_P']  + totals['F_vs_C']  + totals['F_vs_D']  + totals['F_vs_X']
    d_a_t = totals['D_vs_P']  + totals['D_vs_C']  + totals['D_vs_D']  + totals['D_vs_X']
    da_t  = totals['DA_vs_P'] + totals['DA_vs_C'] + totals['DA_vs_D'] + totals['DA_vs_X']
    p_t   = totals['SA_vs_P'] + totals['F_vs_P']  + totals['D_vs_P']  + totals['DA_vs_P']
    c_t   = totals['SA_vs_C'] + totals['F_vs_C']  + totals['D_vs_C']  + totals['DA_vs_C']
    d_d_t = totals['SA_vs_D'] + totals['F_vs_D']  + totals['D_vs_D']  + totals['DA_vs_D']
    x_t   = totals['SA_vs_X'] + totals['F_vs_X']  + totals['D_vs_X']  + totals['DA_vs_X']

    return {
        'SA':         sa_t  / tm * 100,
        'Feint':      f_t   / tm * 100,
        'Dodge(atk)': d_a_t / tm * 100,
        'DA':         da_t  / tm * 100,
        'Parry':      p_t   / tm * 100,
        'Counter':    c_t   / tm * 100,
        'Dodge(def)': d_d_t / tm * 100,
        'Defenseless': x_t  / tm * 100,
    }


def check_diversity(finals, advanced):
    flags = []

    s = finals[0][0]
    for name, val in [
        ('dp_atk',    s.dodge_prob_atk),
        ('dp_vs_low', s.dodge_prob_vs_low),
        ('dp_vs_high', s.dodge_prob_vs_high),
        ('cp_vs_low', s.counter_prob_vs_low),
        ('cp_vs_high', s.counter_prob_vs_high),
    ]:
        if val >= DP_THRESHOLD:
            flags.append(f"{name}={val:.2f} >= 99%")

    marginals = compute_marginals(finals)
    skip = set() if advanced else {'DA'}
    for name, pct in marginals.items():
        if name in skip:
            continue
        if pct < MARGINAL_THRESHOLD:
            flags.append(f"{name}={pct:.1f}% < 5%")

    return flags, marginals


def run_sweep():
    all_warnings = []
    total = len(DICE_VALUES) * len(BONUS_COMBOS) * len(MANEUVER_MODES)
    run_n = 0

    for dice in DICE_VALUES:
        for (wb, ab) in BONUS_COMBOS:
            for advanced in MANEUVER_MODES:
                run_n += 1
                adv_str = "adv=ON " if advanced else "adv=OFF"
                label = f"dice={dice:2d}  wpn={wb}  arm={ab}  {adv_str}"
                print(f"\n{'='*62}")
                print(f"[{run_n:2d}/{total}]  {label}")
                print('='*62)

                patch_globals(wb, ab, advanced)
                random.seed(42)
                finals = evolve(hd=dice, **EVOLVE_KWARGS)

                flags, marginals = check_diversity(finals, advanced)
                s, wr, *_ = finals[0]

                print(f"Top WR: {wr:.3f}  |  "
                      f"dp_a={s.dodge_prob_atk:.2f}  "
                      f"cp_lo={s.counter_prob_vs_low:.2f}  "
                      f"cp_hi={s.counter_prob_vs_high:.2f}")
                print(f"Atk: SA={marginals['SA']:5.1f}%  "
                      f"Feint={marginals['Feint']:5.1f}%  "
                      f"Dodge={marginals['Dodge(atk)']:5.1f}%  "
                      f"DA={marginals['DA']:5.1f}%")
                print(f"Def: Parry={marginals['Parry']:5.1f}%  "
                      f"Counter={marginals['Counter']:5.1f}%  "
                      f"Dodge={marginals['Dodge(def)']:5.1f}%  "
                      f"Defenseless={marginals['Defenseless']:5.1f}%")

                if flags:
                    print(f"*** WARNINGS: {', '.join(flags)}")
                    all_warnings.append((label, flags))
                else:
                    print("OK")

    print(f"\n{'#'*62}")
    print("SWEEP COMPLETE — SUMMARY")
    print('#'*62)
    if all_warnings:
        print(f"\n{len(all_warnings)} of {total} configurations flagged:\n")
        for label, flags in all_warnings:
            print(f"  {label}")
            for f in flags:
                print(f"    - {f}")
    else:
        print("\nNo diversity concerns found across all configurations.")


if __name__ == "__main__":
    run_sweep()
