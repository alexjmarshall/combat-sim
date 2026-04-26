"""Sequential game evolution and degenerate strategy detection."""

import random
import statistics
from collections import defaultdict
from strategy_seq import SequentialStrategy, run_combat_sequential, COMBATANT_DICE


def evaluate_seq(strat, opps, n=3, hd=COMBATANT_DICE, track=False):
    wins = losses = draws = 0
    te = 0
    resp_parry = defaultdict(int)
    resp_counter = defaultdict(int)
    resp_dodge = defaultdict(int)
    def_dist = defaultdict(int)
    commits_atk = []
    commits_def = []
    turns = []
    hit_damages = []
    bout_max_damages = []
    first_blood_losses = first_blood_total = 0
    for opp in opps:
        for _ in range(n):
            w, t, s = run_combat_sequential(strat, opp, hd_a=hd, hd_b=hd, track_stats=track)
            if w == 0:
                wins += 1
            elif w == 1:
                losses += 1
            else:
                draws += 1
            if track:
                te += s['total_exchanges']
                for k, v in s['response_to_parry'].items():
                    resp_parry[k] += v
                for k, v in s['response_to_counter'].items():
                    resp_counter[k] += v
                for k, v in s['response_to_dodge'].items():
                    resp_dodge[k] += v
                for k, v in s['def_maneuver_dist'].items():
                    def_dist[k] += v
                commits_atk.extend(s['commits_atk'])
                commits_def.extend(s['commits_def'])
                turns.append(t)
                hit_damages.extend(s['hit_damages'])
                bout_max_damages.append(s['bout_max_damage'])
                if s['first_blood_loser'] is not None and w in (0, 1):
                    first_blood_total += 1
                    if s['first_blood_loser'] != w:
                        first_blood_losses += 1
    total = wins + losses + draws
    wr = (wins + 0.5 * draws) / max(1, total)
    first_blood_loser_rate = first_blood_losses / max(1, first_blood_total)
    return wr, te, resp_parry, resp_counter, resp_dodge, def_dist, \
           commits_atk, commits_def, turns, hit_damages, bout_max_damages, first_blood_loser_rate


def tournament(pf, k=5):
    return max(random.sample(pf, min(k, len(pf))), key=lambda x: x[1])[0]


def evolve_seq(pop_size=60, gens=40, games=3, opps_n=10, hd=COMBATANT_DICE,
               mut=0.06, elite=0.1, verbose=True):
    pop = [SequentialStrategy.random() for _ in range(pop_size)]
    for gen in range(gens):
        pf = []
        for s in pop:
            opps = random.sample(pop, min(opps_n, len(pop) -- 1))
            wr, *_ = evaluate_seq(s, opps, n=games, hd=hd)
            pf.append((s, wr))
        pf.sort(key=lambda x: x[1], reverse=True)

        if verbose and gen % 5 == 0:
            fpt = statistics.mean(s.feint_parry_threshold for s, _ in pf)
            dct = statistics.mean(s.dodge_counter_threshold for s, _ in pf)
            ac  = statistics.mean(s.attack_commit_frac for s, _ in pf)
            cp_lo = statistics.mean(s.counter_prob_vs_low for s, _ in pf)
            cp_hi = statistics.mean(s.counter_prob_vs_high for s, _ in pf)
            p_lo = statistics.mean(s.parry_commit_vs_low_frac for s, _ in pf)
            p_hi = statistics.mean(s.parry_commit_vs_high_frac for s, _ in pf)
            print(f"Gen {gen:3d}: feint_parry_t={fpt:.2f} dodge_ctr_t={dct:.2f} commit={ac:.2f} | "
                  f"cp_lo={cp_lo:.2f} cp_hi={cp_hi:.2f} p_lo={p_lo:.2f} p_hi={p_hi:.2f}")

        ec = max(1, int(pop_size * elite))
        new_pop = [s for s, _ in pf[:ec]]
        while len(new_pop) < pop_size:
            new_pop.append(SequentialStrategy.crossover(tournament(pf), tournament(pf)).mutate(mut))
        pop = new_pop

    finals = []
    for s in pop:
        opps = random.sample(pop, min(20, len(pop)))
        result = evaluate_seq(s, opps, n=15, hd=hd, track=True)
        finals.append((s, *result))
    finals.sort(key=lambda x: x[1], reverse=True)
    return finals


def report_seq(finals, label=""):
    print("\n" + "=" * 70)
    print(f"SEQUENTIAL RESULTS{': ' + label if label else ''}")
    print("=" * 70)

    te = 0
    agg_rp = defaultdict(int)
    agg_rc = defaultdict(int)
    agg_rd = defaultdict(int)
    agg_dd = defaultdict(int)
    all_ca = []
    all_cd = []
    all_turns = []
    all_hit_damages = []
    all_bout_max_damages = []
    all_fbr = []

    for entry in finals[:10]:
        s, wr, tc, rp, rc, rd, dd, ca, cd, turns, hit_damages, bout_max_damages, fbr = entry
        te += tc
        for k, v in rp.items():
            agg_rp[k] += v
        for k, v in rc.items():
            agg_rc[k] += v
        for k, v in rd.items():
            agg_rd[k] += v
        for k, v in dd.items():
            agg_dd[k] += v
        all_ca.extend(ca)
        all_cd.extend(cd)
        all_turns.extend(turns)
        all_hit_damages.extend(hit_damages)
        all_bout_max_damages.extend(bout_max_damages)
        all_fbr.append(fbr)

    print(f"\nDefense distribution ({te} exchanges, top 10):")
    total_def = max(1, sum(agg_dd.values()))
    for k in ('Parry', 'Counter', 'Dodge', 'Defenseless'):
        print(f"  {k}: {agg_dd[k]/total_def*100:5.1f}%")

    print(f"\nAttacker response distribution:")
    p_total = max(1, sum(agg_rp.values()))
    c_total = max(1, sum(agg_rc.values()))
    d_total = max(1, sum(agg_rd.values()))
    print(f"  vs Parry:   Feint {agg_rp['Feint']/p_total*100:.1f}%  SA {agg_rp['SA']/p_total*100:.1f}%")
    print(f"  vs Counter: SA {agg_rc['SA']/c_total*100:.1f}%  Dodge {agg_rc['Dodge']/c_total*100:.1f}%")
    print(f"  vs Dodge:   SA {agg_rd['SA']/d_total*100:.1f}%")

    if all_ca:
        print(f"\nAvg commits: atk={statistics.mean(all_ca):.2f}  def={statistics.mean(all_cd):.2f}")
    if all_turns:
        print(f"Pace: {statistics.mean(all_turns):.2f} turns/combat, "
              f"{te/max(1,len(all_turns)):.2f} exchanges/combat")
    if all_hit_damages:
        print(f"Damage: median hit={statistics.median(all_hit_damages):.1f}, "
              f"median bout max={statistics.median(all_bout_max_damages):.1f}")
    if all_fbr:
        print(f"Death spiral: first-blood loser rate={statistics.mean(all_fbr):.1%} "
              f"(50%=none, 100%=instant)")

    print(f"\n{'-'*50}")
    print("DOMINANCE ANALYSIS")
    print(f"{'-'*50}")

    warnings = []
    if agg_rp['Feint'] / p_total > 0.90:
        warnings.append("WARNING: Feint dominates vs Parry (>90%) -- Parry may be degenerate")
    if agg_rp['SA'] / p_total > 0.90:
        warnings.append("WARNING: SA dominates vs Parry (>90%) -- Feint offers no value against Parry")
    if agg_rc['SA'] / c_total > 0.90:
        warnings.append("WARNING: SA dominates vs Counter (>90%) -- Dodge is never worth using")
    if agg_rc['Dodge'] / c_total > 0.90:
        warnings.append("WARNING: Dodge dominates vs Counter (>90%) -- accepting a counter is never optimal")
    for k in ('Parry', 'Counter', 'Dodge'):
        if agg_dd[k] / total_def < 0.03:
            warnings.append(f"WARNING: {k} nearly absent (<3% of defenses) -- degenerate defense")

    if warnings:
        for w in warnings:
            print(w)
    else:
        print("No dominant or degenerate patterns detected.")

    top10 = [s for s, *_ in finals[:10]]
    fpt_vals = [s.feint_parry_threshold for s in top10]
    dct_vals = [s.dodge_counter_threshold for s in top10]
    print(f"\nThreshold clustering (top-10 strategies):")
    if len(fpt_vals) >= 2:
        print(f"  feint_parry_threshold:   mean={statistics.mean(fpt_vals):.3f}  "
              f"stdev={statistics.stdev(fpt_vals):.3f}")
        print(f"  dodge_counter_threshold: mean={statistics.mean(dct_vals):.3f}  "
              f"stdev={statistics.stdev(dct_vals):.3f}")
        if statistics.stdev(fpt_vals) < 0.05:
            print("  NOTE: feint_parry_threshold tightly clustered -- strong convergence on a single value")
        if statistics.stdev(dct_vals) < 0.05:
            print("  NOTE: dodge_counter_threshold tightly clustered -- strong convergence on a single value")
    else:
        print(f"  feint_parry_threshold:   {fpt_vals[0]:.3f}")
        print(f"  dodge_counter_threshold: {dct_vals[0]:.3f}")

    s, wr, *_ = finals[0]
    print(f"\nTop strategy (win rate {wr:.3f}):")
    print(f"  attack_commit={s.attack_commit_frac:.2%}")
    print(f"  feint_parry_threshold={s.feint_parry_threshold:.3f}  "
          f"feint_followup={s.feint_followup_vs_parry_frac:.2%}")
    print(f"  dodge_counter_threshold={s.dodge_counter_threshold:.3f}  "
          f"dodge_roll={s.dodge_roll_frac:.2%}")
    print(f"  def: threshold={s.commit_ratio_threshold:.2%}")
    print(f"  vs LOW: cp={s.counter_prob_vs_low:.2%} p_c={s.parry_commit_vs_low_frac:.2%} "
          f"c_c={s.counter_commit_vs_low_frac:.2%} dp={s.dodge_prob_vs_low:.2%}")
    print(f"  vs HI:  cp={s.counter_prob_vs_high:.2%} p_c={s.parry_commit_vs_high_frac:.2%} "
          f"c_c={s.counter_commit_vs_high_frac:.2%} dp={s.dodge_prob_vs_high:.2%}")


if __name__ == "__main__":
    random.seed(42)
    print("Sequential game evolution")
    finals = evolve_seq(pop_size=60, gens=40, games=3, opps_n=10, hd=COMBATANT_DICE, verbose=True)
    report_seq(finals, "Sequential")
