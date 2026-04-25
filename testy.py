import random
import math

def roll_successes(n):
    return sum(1 for _ in range(n) if random.randint(1, 6) >= 5)

def split_dice(total, n):
    if total <= 0:
        return []
    if n > total:
        n = total
    base, rem = total // n, total % n
    return [base + 1] * rem + [base] * (n - rem)

def simulate_fixed_pools(strat_a, strat_b, first_turn_penalty, refresh_mode="start"):
    D_a, N_a = strat_a
    D_b, N_b = strat_b
    # refresh_mode: "start" (attacker refreshes at start of own turn),
    #               "end"   (attacker refreshes at end of own turn),
    #               "both"  (both sides refresh at start of every turn)
    side_a_max = 10
    side_b_max = 10

    # Available pool of fresh dice
    a_pool = side_a_max
    b_pool = side_b_max

    turn = random.choice(['a', 'b'])
    initiative = turn
    if turn == 'a':
        b_pool = math.floor(side_b_max * first_turn_penalty)
    else:
        a_pool = math.floor(side_a_max * first_turn_penalty)

    while side_a_max > 0 and side_b_max > 0:
        # Start-of-turn refreshes
        if refresh_mode in ("start", "both"):
            if turn == 'a':
                a_pool = side_a_max
            else:
                b_pool = side_b_max
        if refresh_mode == "both":
            # Defender also refreshes
            if turn == 'a':
                b_pool = side_b_max
            else:
                a_pool = side_a_max

        if turn == 'a':
            D_eff = min(D_a, max(0, a_pool))
            if D_eff <= 0:
                if refresh_mode == "end":
                    a_pool = side_a_max
                turn = 'b'
                continue

            atk_splits = split_dice(D_eff, N_a)
            N_eff = len(atk_splits)
            a_pool -= D_eff

            if refresh_mode == "end":
                def_total = min(D_eff, max(0, b_pool))
            else:
                def_total = max(0, b_pool)
            def_splits = split_dice(def_total, N_eff)
            while len(def_splits) < N_eff:
                def_splits.append(0)
            b_pool -= def_total

            for atk_n, def_n in zip(atk_splits, def_splits):
                damage = max(0, roll_successes(atk_n) - roll_successes(def_n))
                side_b_max -= damage
                b_pool = max(0, b_pool - damage)
                if side_b_max <= 0 or damage == 0:
                    break

            if refresh_mode == "end":
                a_pool = side_a_max
            turn = 'b'

        else:
            D_eff = min(D_b, max(0, b_pool))
            if D_eff <= 0:
                if refresh_mode == "end":
                    b_pool = side_b_max
                turn = 'a'
                continue

            atk_splits = split_dice(D_eff, N_b)
            N_eff = len(atk_splits)
            b_pool -= D_eff

            if refresh_mode == "end":
                def_total = min(D_eff, max(0, a_pool))
            else:
                def_total = max(0, a_pool)
            def_splits = split_dice(def_total, N_eff)
            while len(def_splits) < N_eff:
                def_splits.append(0)
            a_pool -= def_total

            for atk_n, def_n in zip(atk_splits, def_splits):
                damage = max(0, roll_successes(atk_n) - roll_successes(def_n))
                side_a_max -= damage
                a_pool = max(0, a_pool - damage)
                if side_a_max <= 0 or damage == 0:
                    break

            if refresh_mode == "end":
                b_pool = side_b_max
            turn = 'a'

    return ('a' if side_a_max > 0 else 'b'), initiative

# --- CONFIGURATION ---
PENALTY = 0.5  # 0.5 means defender starts with 5 dice instead of 10, 1 means they start with 10 dice
REFRESH_MODE = "start"  # "start", "end", or "both"
TRIALS = 1000

print(f"--- Random initiative | Refresh: {REFRESH_MODE} | Penalty: {PENALTY} ---")
print(f"Strategy = (D, N): D total dice committed per turn, split across N sub-attacks.")
print(f"A's win rate over {TRIALS} games per cell.\n")

strategies = [(D, N) for D in range(1, 11) for N in range(1, D + 1)]
results = {}
init_wins = 0
total_games = 0
for sa in strategies:
    for sb in strategies:
        wins = 0
        for _ in range(TRIALS):
            winner, initiative = simulate_fixed_pools(sa, sb, PENALTY, REFRESH_MODE)
            if winner == 'a':
                wins += 1
            if winner == initiative:
                init_wins += 1
            total_games += 1
        results[(sa, sb)] = wins / TRIALS

worst = {sa: min(results[(sa, sb)] for sb in strategies) for sa in strategies}
worst_counter = {sa: min(strategies, key=lambda sb: results[(sa, sb)]) for sa in strategies}

best_sa = max(strategies, key=lambda sa: worst[sa])
bc = worst_counter[best_sa]
print(f"Overall maximin strategy: D={best_sa[0]}, N={best_sa[1]}"
      f" -> guaranteed A-win >= {worst[best_sa]*100:.1f}%"
      f"  (worst counter: D={bc[0]}, N={bc[1]})")

print("\nGiven N attacks, best total dice D:")
for N_fixed in range(1, 11):
    candidates = [sa for sa in strategies if sa[1] == N_fixed]
    if not candidates:
        continue
    best = max(candidates, key=lambda sa: worst[sa])
    bc = worst_counter[best]
    print(f"  N={N_fixed}: best D={best[0]}, maximin={worst[best]*100:5.1f}%"
          f"  (worst counter: D={bc[0]}, N={bc[1]})")

print("\nGiven D total dice, best number of attacks N:")
for D_fixed in range(1, 11):
    candidates = [sa for sa in strategies if sa[0] == D_fixed]
    best = max(candidates, key=lambda sa: worst[sa])
    bc = worst_counter[best]
    print(f"  D={D_fixed}: best N={best[1]}, maximin={worst[best]*100:5.1f}%"
          f"  (worst counter: D={bc[0]}, N={bc[1]})")

print("\nTop 5 strategies by maximin:")
for sa in sorted(strategies, key=lambda sa: worst[sa], reverse=True)[:5]:
    print(f"  (D={sa[0]}, N={sa[1]}) -> {worst[sa]*100:5.1f}%")

print(f"\nInitiative-holder win rate: {init_wins/total_games*100:.1f}% over {total_games} games")
print(f"  (50% = initiative is neutral; higher = first-mover advantage)")