"""Standalone analysis script — processes raw JSON to answer the data questions.

Run from the project root:
    python backend/scripts/analyze_lineups.py
"""

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / 'raw_data'

AGGREGATION_FIELDS = (
    'fg2_made', 'fg2_attempted', 'fg3_made', 'fg3_attempted',
    'fg_made', 'fg_attempted', 'ft_made', 'ft_attempted',
    'rebounds_offense', 'rebounds_defense', 'rebound_opportunities',
    'assists', 'steals', 'turnovers', 'blocks',
    'offensive_fouls', 'defensive_fouls', 'shooting_fouls',
    'points', 'shot_attempts', 'shot_attempt_points',
    'ft_potential_points', 'transition_take_fouls',
)


def load_json(filename):
    with open(RAW_DATA_DIR / filename) as f:
        return json.load(f)


def safe_div(n, d):
    return n / d if d else 0.0


def build_lineups(possessions, players_map, teams_map, lineup_size=5):
    lineup_data = {}

    for poss in possessions:
        off_ids = sorted(poss['offensive_player_ids'])
        def_ids = sorted(poss['defensive_player_ids'])
        stat_vals = {f: poss[f] for f in AGGREGATION_FIELDS}

        for combo in combinations(off_ids, lineup_size):
            entry = lineup_data.get(combo)
            if entry is None:
                entry = {'off': defaultdict(float), 'def': defaultdict(float),
                         'off_poss': 0, 'def_poss': 0}
                lineup_data[combo] = entry
            entry['off_poss'] += 1
            for f, v in stat_vals.items():
                entry['off'][f] += v

        for combo in combinations(def_ids, lineup_size):
            entry = lineup_data.get(combo)
            if entry is None:
                entry = {'off': defaultdict(float), 'def': defaultdict(float),
                         'off_poss': 0, 'def_poss': 0}
                lineup_data[combo] = entry
            entry['def_poss'] += 1
            for f, v in stat_vals.items():
                entry['def'][f] += v

    results = []
    for combo, data in lineup_data.items():
        off_poss = data['off_poss']
        def_poss = data['def_poss']
        total_poss = off_poss + def_poss
        if total_poss == 0:
            continue

        off_pts = int(data['off']['points'])
        def_pts = int(data['def']['points'])

        off_rtg = round(safe_div(off_pts, off_poss) * 100, 1)
        def_rtg = round(safe_div(def_pts, def_poss) * 100, 1)
        net_rtg = round(off_rtg - def_rtg, 1)

        off_fg_att = int(data['off']['fg_attempted'])
        off_fg_made = int(data['off']['fg_made'])
        off_fg3_made = int(data['off']['fg3_made'])
        off_ft_att = int(data['off']['ft_attempted'])
        def_fg_att = int(data['def']['fg_attempted'])
        def_fg_made = int(data['def']['fg_made'])
        def_fg3_made = int(data['def']['fg3_made'])
        def_ft_att = int(data['def']['ft_attempted'])

        off_efg = safe_div(off_fg_made + 0.5 * off_fg3_made, off_fg_att)
        def_efg = safe_div(def_fg_made + 0.5 * def_fg3_made, def_fg_att)

        off_tsa = off_fg_att + 0.44 * off_ft_att
        off_ts = safe_div(off_pts, 2 * off_tsa) if off_tsa else 0

        off_tov = int(data['off']['turnovers'])
        off_plays = off_fg_att + 0.44 * off_ft_att + off_tov
        off_tov_pct = safe_div(off_tov, off_plays)

        off_oreb = int(data['off']['rebounds_offense'])
        off_oreb_opp = int(data['off']['rebound_opportunities'])
        off_oreb_pct = safe_div(off_oreb, off_oreb_opp)

        def_dreb = int(data['def']['rebounds_defense'])
        def_dreb_opp = int(data['def']['rebound_opportunities'])
        def_dreb_pct = safe_div(def_dreb, def_dreb_opp)

        team_id = players_map[combo[0]]['team_id']
        team_name = teams_map.get(team_id, 'Unknown')
        names = [players_map[pid]['name'] for pid in combo]

        results.append({
            'combo': combo,
            'names': names,
            'team': team_name,
            'team_id': team_id,
            'off_poss': off_poss,
            'def_poss': def_poss,
            'total_poss': total_poss,
            'off_pts': off_pts,
            'def_pts': def_pts,
            'plus_minus': off_pts - def_pts,
            'off_rtg': off_rtg,
            'def_rtg': def_rtg,
            'net_rtg': net_rtg,
            'off_efg': off_efg,
            'def_efg': def_efg,
            'off_ts': off_ts,
            'off_tov_pct': off_tov_pct,
            'off_oreb_pct': off_oreb_pct,
            'def_dreb_pct': def_dreb_pct,
            'off_reb_off': off_oreb,
            'off_reb_opp': off_oreb_opp,
            'def_reb_def': def_dreb,
            'def_reb_opp': def_dreb_opp,
            'off_steals': int(data['off']['steals']),
            'def_steals': int(data['def']['steals']),
            'off_blocks': int(data['off']['blocks']),
            'def_blocks': int(data['def']['blocks']),
            'off_assists': int(data['off']['assists']),
            'def_fg3_att': int(data['def']['fg3_attempted']),
            'def_fg3_made': def_fg3_made,
            'off_fg3_att': int(data['off']['fg3_attempted']),
            'off_fg3_made': off_fg3_made,
        })

    return results


def build_player_stats(possessions, players_map, teams_map):
    """Build 1-man lineup stats to evaluate individual player impact."""
    return build_lineups(possessions, players_map, teams_map, lineup_size=1)


def main():
    players_raw = load_json('players.json')
    teams_raw = load_json('teams.json')
    possessions = load_json('possessions.json')

    players_map = {p['player_id']: p for p in players_raw}
    teams_map = {t['team_id']: t['name'] for t in teams_raw}

    # ── Question 1: Best 5-man lineup by on-court impact ───────────────
    print('=' * 80)
    print('QUESTION 1: Which 5-man lineup has the most positive on-court impact?')
    print('=' * 80)

    lineups_5 = build_lineups(possessions, players_map, teams_map, lineup_size=5)
    lineups_5.sort(key=lambda x: x['net_rtg'], reverse=True)

    print(f'\nTotal 5-man lineups: {len(lineups_5)}')
    print('\nTop 10 by Net Rating:')
    print(f'{"Rank":<5} {"Net RTG":<10} {"Off RTG":<10} {"Def RTG":<10} {"POSS":<8} {"+/-":<8} {"Team":<20} {"Players"}')
    print('-' * 120)
    for i, lu in enumerate(lineups_5[:10], 1):
        print(f'{i:<5} {lu["net_rtg"]:<10} {lu["off_rtg"]:<10} {lu["def_rtg"]:<10} '
              f'{lu["total_poss"]:<8} {lu["plus_minus"]:<8} {lu["team"]:<20} {", ".join(lu["names"])}')

    # Also show top by net rating with minimum possessions
    min_poss_thresholds = [4, 8, 12]
    for min_p in min_poss_thresholds:
        filtered = [lu for lu in lineups_5 if lu['total_poss'] >= min_p]
        if filtered:
            best = filtered[0]
            print(f'\nBest with min {min_p} poss: Net RTG {best["net_rtg"]}, '
                  f'Poss={best["total_poss"]}, +/-={best["plus_minus"]}, '
                  f'Team={best["team"]}, Players={", ".join(best["names"])}')

    # ── Question 2: Best individual player by on-court impact ──────────
    print('\n' + '=' * 80)
    print('QUESTION 2: Which player has the most positive on-court impact?')
    print('=' * 80)

    player_stats = build_player_stats(possessions, players_map, teams_map)
    player_stats.sort(key=lambda x: x['net_rtg'], reverse=True)

    print(f'\nTotal players: {len(player_stats)}')
    print('\nTop 15 by Net Rating:')
    print(f'{"Rank":<5} {"Net RTG":<10} {"Off RTG":<10} {"Def RTG":<10} {"POSS":<8} {"+/-":<8} {"Team":<20} {"Player"}')
    print('-' * 100)
    for i, ps in enumerate(player_stats[:15], 1):
        print(f'{i:<5} {ps["net_rtg"]:<10} {ps["off_rtg"]:<10} {ps["def_rtg"]:<10} '
              f'{ps["total_poss"]:<8} {ps["plus_minus"]:<8} {ps["team"]:<20} {ps["names"][0]}')

    # ── Question 3: Counter to rebounding-heavy lineup ─────────────────
    print('\n' + '=' * 80)
    print('QUESTION 3: Best counter to a rebounding-heavy big lineup?')
    print('=' * 80)

    # Score lineups on counter-rebounding ability:
    # - High defensive rebound % (deny opponent offensive rebounds)
    # - Low opponent offensive rebound opportunities
    # - High 3PT shooting (pull bigs away from rim, reduce rebound value)
    # - Good steals/blocks (disruptive defense)
    # - Fast pace (exploit slow bigs in transition)

    for lu in lineups_5:
        lu['counter_score'] = (
            lu['def_dreb_pct'] * 30 +               # Defensive rebounding
            lu['off_efg'] * 20 +                      # Efficient offense (beating the glass with shooting)
            (lu['off_fg3_made'] / max(lu['off_poss'], 1)) * 15 +  # 3PT frequency
            (lu['off_steals'] + lu['def_steals']) / max(lu['total_poss'], 1) * 20 +  # Turnovers forced
            lu['off_ts'] * 15                          # True shooting efficiency
        )

    lineups_5.sort(key=lambda x: x['counter_score'], reverse=True)

    print('\nTop 10 counter lineups (composite score):')
    print(f'{"Rank":<5} {"Score":<8} {"DREB%":<8} {"3PM/P":<8} {"eFG%":<8} {"Net":<8} {"POSS":<6} {"Team":<20} {"Players"}')
    print('-' * 130)
    for i, lu in enumerate(lineups_5[:10], 1):
        fg3_per_poss = lu['off_fg3_made'] / max(lu['off_poss'], 1)
        print(f'{i:<5} {lu["counter_score"]:.2f}   '
              f'{lu["def_dreb_pct"]:.3f}   '
              f'{fg3_per_poss:.3f}   '
              f'{lu["off_efg"]:.3f}   '
              f'{lu["net_rtg"]:<8} '
              f'{lu["total_poss"]:<6} '
              f'{lu["team"]:<20} '
              f'{", ".join(lu["names"])}')

    # Also show per-team best counter
    print('\nBest counter per team:')
    team_best = {}
    for lu in lineups_5:
        t = lu['team']
        if t not in team_best:
            team_best[t] = lu
    for team, lu in sorted(team_best.items()):
        fg3_per_poss = lu['off_fg3_made'] / max(lu['off_poss'], 1)
        print(f'  {team:<20} DREB%={lu["def_dreb_pct"]:.3f} 3PM/P={fg3_per_poss:.3f} '
              f'Net={lu["net_rtg"]} Poss={lu["total_poss"]} → {", ".join(lu["names"])}')


if __name__ == '__main__':
    main()
