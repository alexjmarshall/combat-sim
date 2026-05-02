import random
import math

def roll_successes(n):
    return sum(1 for _ in range(n) if random.randint(1, 6) >= 5)

def simulate(D_a, D_b, pool_a, pool_b, first_turn_penalty, refresh_mode="start", carryover=True):
    # refresh_mode: "start" (attacker refreshes at start of own turn),
    #               "end"   (attacker refreshes at end of own turn),
    #               "both"  (both sides refresh at start of every turn)
    side_a_max = pool_a
    side_b_max = pool_b

    side_a_hp = side_a_max
    side_b_hp = side_b_max
    damage_pool_a = 0
    damage_pool_b = 0

    a_pool = side_a_max
    b_pool = side_b_max

    turn = random.choice(['a', 'b'])
    initiative = turn
    if turn == 'a':
        b_pool = math.floor(side_b_max * first_turn_penalty)
    else:
        a_pool = math.floor(side_a_max * first_turn_penalty)

    def refresh(pool, side_max):
        return pool + side_max if carryover else side_max

    def defend(D_eff, defender_pool):
        # carryover: only spend what's needed (save rest for next turn)
        # no carryover: spend everything (nothing to save anyway)
        if carryover:
            return min(D_eff, max(0, defender_pool))
        else:
            return max(0, defender_pool)

    while side_a_max > 0 and side_b_max > 0:
        if refresh_mode in ("start", "both"):
            if turn == 'a':
                a_pool = refresh(a_pool, side_a_max)
            else:
                b_pool = refresh(b_pool, side_b_max)
        if refresh_mode == "both":
            if turn == 'a':
                b_pool = refresh(b_pool, side_b_max)
            else:
                a_pool = refresh(a_pool, side_a_max)

        if turn == 'a':
            D_eff = min(D_a, max(0, a_pool))
            if D_eff <= 0:
                if refresh_mode == "end":
                    a_pool = refresh(a_pool, side_a_max)
                turn = 'b'
                continue

            a_pool -= D_eff
            def_total = defend(D_eff, b_pool)
            b_pool -= def_total

            damage = max(0, roll_successes(D_eff) - roll_successes(def_total))
            if DAMAGE_POOL_MODE:
                damage_pool_b += damage
                if damage_pool_b >= side_b_hp:
                    side_b_max = 0
            else:
                side_b_max -= damage
                b_pool = max(0, b_pool - damage)

            if refresh_mode == "end":
                a_pool = refresh(a_pool, side_a_max)
            turn = 'b'

        else:
            D_eff = min(D_b, max(0, b_pool))
            if D_eff <= 0:
                if refresh_mode == "end":
                    b_pool = refresh(b_pool, side_b_max)
                turn = 'a'
                continue

            b_pool -= D_eff
            def_total = defend(D_eff, a_pool)
            a_pool -= def_total

            damage = max(0, roll_successes(D_eff) - roll_successes(def_total))
            if DAMAGE_POOL_MODE:
                damage_pool_a += damage
                if damage_pool_a >= side_a_hp:
                    side_a_max = 0
            else:
                side_a_max -= damage
                a_pool = max(0, a_pool - damage)

            if refresh_mode == "end":
                b_pool = refresh(b_pool, side_b_max)
            turn = 'a'

    return ('a' if side_a_max > 0 else 'b'), initiative

# --- CONFIGURATION ---
DAMAGE_POOL_MODE = True  # False: damage removes dice directly; True: damage accumulates, death when total >= starting dice
PENALTY = 0.5
REFRESH_MODE = "start"  # "start", "end", or "both"
CARRYOVER = True        # True: leftover defense dice carry to next attack turn
                        # False: spend all dice on defense, nothing carried over
TRIALS = 500
ENEMY_POOL = 10
PLAYER_POOLS = [6, 8, 10, 12, 15, 20]

carryover_label = "carryover" if CARRYOVER else "use-or-lose"
print(f"--- Refresh: {REFRESH_MODE} | Penalty: {PENALTY} | Enemy pool: {ENEMY_POOL} | Defense: {carryover_label} ---")
print(f"Finding maximin offense dice D for player at each pool size.\n", flush=True)

print(f"{'Pool':>6} {'Best D':>7} {'Hold back':>10} {'Guaranteed win%':>16} {'Worst counter':>14}")
print("-" * 58)

for pool_a in PLAYER_POOLS:
    strats_a = list(range(1, pool_a + 1))
    strats_b = list(range(1, ENEMY_POOL + 1))
    results = {}

    for D_a in strats_a:
        for D_b in strats_b:
            wins = sum(
                1 for _ in range(TRIALS)
                if simulate(D_a, D_b, pool_a, ENEMY_POOL, PENALTY, REFRESH_MODE, CARRYOVER)[0] == 'a'
            )
            results[(D_a, D_b)] = wins / TRIALS

    worst = {D: min(results[(D, D_b)] for D_b in strats_b) for D in strats_a}
    best_D = max(strats_a, key=lambda D: worst[D])
    worst_counter = min(strats_b, key=lambda D_b: results[(best_D, D_b)])

    print(f"{pool_a:>6} {best_D:>7} {pool_a - best_D:>10} {worst[best_D]*100:>15.1f}% {worst_counter:>14}")

print()
