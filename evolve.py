"""V4 evolution. Fast iteration — shorter runs for quick testing."""

import random
import statistics
from collections import defaultdict
import combat
from strategy import Strategy, run_combat, COMBATANT_DICE


def evaluate(strat, opps, n=3, hd=COMBATANT_DICE, track=False):
    wins = losses = draws = 0
    te = 0
    mc = defaultdict(int)
    commits = defaultdict(list)
    turns = []
    hit_damages = []
    bout_max_damages = []
    for opp in opps:
        for _ in range(n):
            w, t, s = run_combat(strat, opp, hd_a=hd, hd_b=hd, track_stats=track)
            if w == 0:
                wins += 1
            elif w == 1:
                losses += 1
            else:
                draws += 1
            if track:
                te += s['total_exchanges']
                for k, v in s['maneuvers'].items():
                    mc[k] += v
                for k, v in s['commits_by_maneuver'].items():
                    commits[k].extend(v)
                turns.append(t)
                hit_damages.extend(s['hit_damages'])
                bout_max_damages.append(s['bout_max_damage'])
    total = wins + losses + draws
    return (wins + 0.5*draws)/max(1, total), mc, te, commits, turns, hit_damages, bout_max_damages


def tournament(pf, k=5):
    return max(random.sample(pf, min(k, len(pf))), key=lambda x: x[1])[0]


def evolve(pop_size=60, gens=40, games=3, opps_n=10, hd=COMBATANT_DICE, mut=0.06, elite=0.1, verbose=True):
    pop = [Strategy.random() for _ in range(pop_size)]
    for gen in range(gens):
        pf = []
        for s in pop:
            opps = random.sample(pop, min(opps_n, len(pop) - 1))
            wr, _, _, _, _, _, _ = evaluate(s, opps, n=games, hd=hd)
            pf.append((s, wr))
        pf.sort(key=lambda x: x[1], reverse=True)
        
        if verbose and gen % 5 == 0:
            fp = statistics.mean(s.feint_prob for s, _ in pf)
            sa_c = statistics.mean(s.sa_commit_frac for s, _ in pf)
            f_c = statistics.mean(s.feint_commit_frac for s, _ in pf)
            fu_p = statistics.mean(s.feint_followup_vs_parry_frac for s, _ in pf)
            dp_a = statistics.mean(s.dodge_prob_atk for s, _ in pf)
            dp_lo = statistics.mean(s.dodge_prob_vs_low for s, _ in pf)
            dp_hi = statistics.mean(s.dodge_prob_vs_high for s, _ in pf)
            cp_lo = statistics.mean(s.counter_prob_vs_low for s, _ in pf)
            cp_hi = statistics.mean(s.counter_prob_vs_high for s, _ in pf)
            p_lo = statistics.mean(s.parry_commit_vs_low_frac for s, _ in pf)
            p_hi = statistics.mean(s.parry_commit_vs_high_frac for s, _ in pf)
            print(f"Gen {gen:3d}: fp={fp:.2f} sa_c={sa_c:.2f} f_c={f_c:.2f} fu_p={fu_p:.2f} "
                  f"dp_a={dp_a:.2f} | cp_lo={cp_lo:.2f} cp_hi={cp_hi:.2f} "
                  f"p_lo={p_lo:.2f} p_hi={p_hi:.2f} dp_lo={dp_lo:.2f} dp_hi={dp_hi:.2f}")
        
        ec = max(1, int(pop_size * elite))
        new_pop = [s for s, _ in pf[:ec]]
        while len(new_pop) < pop_size:
            new_pop.append(Strategy.crossover(tournament(pf), tournament(pf)).mutate(mut))
        pop = new_pop
    
    finals = []
    for s in pop:
        opps = random.sample(pop, min(20, len(pop)))
        wr, mc, te, commits, turns, hit_damages, bout_max_damages = evaluate(s, opps, n=15, hd=hd, track=True)
        finals.append((s, wr, mc, te, commits, turns, hit_damages, bout_max_damages))
    finals.sort(key=lambda x: x[1], reverse=True)
    return finals


def report(finals, label=""):
    print("\n" + "=" * 70)
    print(f"RESULTS{': ' + label if label else ''}")
    print("=" * 70)
    
    totals = defaultdict(int)
    te = 0
    all_commits = defaultdict(list)
    all_turns = []
    all_hit_damages = []
    all_bout_max_damages = []
    for s, wr, mc, tc, commits, turns, hit_damages, bout_max_damages in finals[:10]:
        te += tc
        for k, v in mc.items():
            totals[k] += v
        for k, v in commits.items():
            all_commits[k].extend(v)
        all_turns.extend(turns)
        all_hit_damages.extend(hit_damages)
        all_bout_max_damages.extend(bout_max_damages)
    
    print(f"\nManeuver distribution ({te} exchanges, top 10):")
    for k in ['SA_vs_P', 'SA_vs_C', 'SA_vs_D', 'SA_vs_X',
              'F_vs_P', 'F_vs_C', 'F_vs_D', 'F_vs_X',
              'D_vs_P', 'D_vs_C', 'D_vs_D', 'D_vs_X',
              'DA_vs_P', 'DA_vs_C', 'DA_vs_D', 'DA_vs_X']:
        print(f"  {k}: {totals[k]/max(1,te)*100:5.1f}%")

    sa_t = totals['SA_vs_P'] + totals['SA_vs_C'] + totals['SA_vs_D'] + totals['SA_vs_X']
    f_t = totals['F_vs_P'] + totals['F_vs_C'] + totals['F_vs_D'] + totals['F_vs_X']
    d_atk_t = totals['D_vs_P'] + totals['D_vs_C'] + totals['D_vs_D'] + totals['D_vs_X']
    da_t = totals['DA_vs_P'] + totals['DA_vs_C'] + totals['DA_vs_D'] + totals['DA_vs_X']
    p_t = totals['SA_vs_P'] + totals['F_vs_P'] + totals['D_vs_P'] + totals['DA_vs_P']
    c_t = totals['SA_vs_C'] + totals['F_vs_C'] + totals['D_vs_C'] + totals['DA_vs_C']
    d_def_t = totals['SA_vs_D'] + totals['F_vs_D'] + totals['D_vs_D'] + totals['DA_vs_D']
    x_t = totals['SA_vs_X'] + totals['F_vs_X'] + totals['D_vs_X'] + totals['DA_vs_X']
    tm = max(1, te)
    print(f"\nMarginals:")
    print(f"  Attacker: SA {sa_t/tm*100:.1f}% | Feint {f_t/tm*100:.1f}% | Dodge {d_atk_t/tm*100:.1f}% | DA {da_t/tm*100:.1f}%")
    print(f"  Defender: Parry {p_t/tm*100:.1f}% | Counter {c_t/tm*100:.1f}% | "
          f"Dodge {d_def_t/tm*100:.1f}% | Defenseless {x_t/tm*100:.1f}%")

    print(f"\nAvg commits:")
    for k in ['SA', 'F', 'P', 'C', 'D', 'DR', 'DA', 'DA_BONUS', 'EA']:
        if all_commits[k]:
            print(f"  {k}: {statistics.mean(all_commits[k]):.2f} (median {statistics.median(all_commits[k]):.1f})")

    if all_turns:
        print(f"\nPace: {statistics.mean(all_turns):.2f} turns/combat, {te/len(all_turns):.2f} exchanges/combat")

    if all_hit_damages:
        print(f"  Damage: median hit={statistics.median(all_hit_damages):.1f}, "
              f"median bout max={statistics.median(all_bout_max_damages):.1f}")

    s, wr, _, _, _, _, _, _ = finals[0]
    print(f"\nTop strategy (win rate {wr:.3f}):")
    print(f"  feint_p={s.feint_prob:.2%} sa_c={s.sa_commit_frac:.2%} f_c={s.feint_commit_frac:.2%}")
    print(f"  fu_P={s.feint_followup_vs_parry_frac:.2%} fu_C={s.feint_followup_vs_counter_frac:.2%}")
    print(f"  dodge_p={s.dodge_prob_atk:.2%} d_c={s.dodge_commit_atk_frac:.2%} d_r={s.dodge_roll_atk_frac:.2%} ea={s.evasive_atk_frac:.2%}")
    print(f"  def: threshold={s.commit_ratio_threshold:.2%}")
    print(f"  vs LOW: cp={s.counter_prob_vs_low:.2%} p_c={s.parry_commit_vs_low_frac:.2%} c_c={s.counter_commit_vs_low_frac:.2%} "
          f"dp={s.dodge_prob_vs_low:.2%} dc={s.dodge_commit_vs_low_frac:.2%} dr={s.dodge_roll_vs_low_frac:.2%} ea={s.evasive_vs_low_frac:.2%}")
    print(f"  vs HI:  cp={s.counter_prob_vs_high:.2%} p_c={s.parry_commit_vs_high_frac:.2%} c_c={s.counter_commit_vs_high_frac:.2%} "
          f"dp={s.dodge_prob_vs_high:.2%} dc={s.dodge_commit_vs_high_frac:.2%} dr={s.dodge_roll_vs_high_frac:.2%} ea={s.evasive_vs_high_frac:.2%}")


if __name__ == "__main__":
    random.seed(42)
    print("V4 evolution")
    finals = evolve(pop_size=60, gens=40, games=3, opps_n=10, hd=COMBATANT_DICE, verbose=True)
    report(finals, "V4")
