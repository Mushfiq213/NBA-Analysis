from __future__ import annotations

"""Helpers for the lineup summary API."""

from collections import defaultdict
from itertools import combinations
from typing import Any

from app.dbmodels.models import Player, Possession, Team

LineupRecord = dict[str, Any]

# Possession-level stat fields to aggregate.
AGGREGATION_FIELDS = (
    'fg2_made', 'fg2_attempted', 'fg3_made', 'fg3_attempted',
    'fg_made', 'fg_attempted', 'ft_made', 'ft_attempted',
    'rebounds_offense', 'rebounds_defense', 'rebound_opportunities',
    'assists', 'steals', 'turnovers', 'blocks',
    'offensive_fouls', 'defensive_fouls', 'shooting_fouls',
    'points', 'shot_attempts', 'shot_attempt_points',
    'ft_potential_points', 'transition_take_fouls',
)


def _normalize_lineup_size(lineup_size: Any) -> int:
    """Clamp lineup_size to [1, 5]."""
    try:
        normalized = int(lineup_size)
    except (TypeError, ValueError):
        return 5
    return max(1, min(5, normalized))


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division returning *default* when the denominator is zero."""
    return numerator / denominator if denominator else default


def _compute_derived_metrics(record: LineupRecord) -> None:
    """Compute advanced NBA analytics metrics on a lineup record *in-place*.

    Metrics added:
    - Field-goal percentages (overall, 2PT, 3PT) for offense & defense
    - Offensive / Defensive / Net Rating (points per 100 possessions)
    - Effective FG% and True Shooting %
    - Turnover rate, rebound rates, assist rate
    - Plus/minus, points-per-possession, pace, free-throw rate
    """
    off_poss = record['offensive_possessions']
    def_poss = record['defensive_possessions']
    total_poss = record['total_possessions']

    # ── Field-goal percentages ──────────────────────────────────────────
    record['offensive_fg_pct'] = _safe_div(record['offensive_fg_made'], record['offensive_fg_attempted'])
    record['offensive_fg2_pct'] = _safe_div(record['offensive_fg2_made'], record['offensive_fg2_attempted'])
    record['offensive_fg3_pct'] = _safe_div(record['offensive_fg3_made'], record['offensive_fg3_attempted'])
    record['defensive_fg_pct'] = _safe_div(record['defensive_fg_made'], record['defensive_fg_attempted'])
    record['defensive_fg2_pct'] = _safe_div(record['defensive_fg2_made'], record['defensive_fg2_attempted'])
    record['defensive_fg3_pct'] = _safe_div(record['defensive_fg3_made'], record['defensive_fg3_attempted'])

    # ── Offensive / Defensive / Net Rating ──────────────────────────────
    record['offensive_rating'] = round(_safe_div(record['offensive_points'], off_poss) * 100, 1)
    record['defensive_rating'] = round(_safe_div(record['defensive_points'], def_poss) * 100, 1)
    record['net_rating'] = round(record['offensive_rating'] - record['defensive_rating'], 1)

    # ── Effective FG%  =  (FGM + 0.5 × 3PM) / FGA ─────────────────────
    record['offensive_efg_pct'] = _safe_div(
        record['offensive_fg_made'] + 0.5 * record['offensive_fg3_made'],
        record['offensive_fg_attempted'],
    )
    record['defensive_efg_pct'] = _safe_div(
        record['defensive_fg_made'] + 0.5 * record['defensive_fg3_made'],
        record['defensive_fg_attempted'],
    )

    # ── True Shooting %  =  PTS / (2 × (FGA + 0.44 × FTA)) ───────────
    off_tsa = record['offensive_fg_attempted'] + 0.44 * record['offensive_ft_attempted']
    def_tsa = record['defensive_fg_attempted'] + 0.44 * record['defensive_ft_attempted']
    record['offensive_ts_pct'] = _safe_div(record['offensive_points'], 2 * off_tsa) if off_tsa else 0.0
    record['defensive_ts_pct'] = _safe_div(record['defensive_points'], 2 * def_tsa) if def_tsa else 0.0

    # ── Turnover Rate  =  TOV / (FGA + 0.44×FTA + TOV) ────────────────
    off_plays = record['offensive_fg_attempted'] + 0.44 * record['offensive_ft_attempted'] + record['offensive_turnovers']
    def_plays = record['defensive_fg_attempted'] + 0.44 * record['defensive_ft_attempted'] + record['defensive_turnovers']
    record['offensive_tov_pct'] = _safe_div(record['offensive_turnovers'], off_plays)
    record['defensive_tov_pct'] = _safe_div(record['defensive_turnovers'], def_plays)

    # ── Rebound Rates ──────────────────────────────────────────────────
    record['offensive_oreb_pct'] = _safe_div(
        record['offensive_rebounds_offense'], record['offensive_rebound_opportunities'],
    )
    record['defensive_dreb_pct'] = _safe_div(
        record['defensive_rebounds_defense'], record['defensive_rebound_opportunities'],
    )

    # ── Assist Rate  =  AST / FGM ─────────────────────────────────────
    record['offensive_ast_pct'] = _safe_div(record['offensive_assists'], record['offensive_fg_made'])

    # ── Plus / Minus ───────────────────────────────────────────────────
    record['plus_minus'] = record['offensive_points'] - record['defensive_points']

    # ── Points per Possession ──────────────────────────────────────────
    record['offensive_ppp'] = round(_safe_div(record['offensive_points'], off_poss), 3)
    record['defensive_ppp'] = round(_safe_div(record['defensive_points'], def_poss), 3)

    # ── Pace (possessions per 48 minutes) ──────────────────────────────
    total_seconds = record.get('total_seconds', 0)
    if total_seconds > 0:
        record['pace'] = round((total_poss / total_seconds) * 48 * 60, 1)
    else:
        record['pace'] = 0.0

    # ── Free-throw Rate  =  FTA / FGA ─────────────────────────────────
    record['offensive_ft_rate'] = _safe_div(record['offensive_ft_attempted'], record['offensive_fg_attempted'])
    record['defensive_ft_rate'] = _safe_div(record['defensive_ft_attempted'], record['defensive_fg_attempted'])


def get_lineup_league_summary_stats(
    lineup_size: int = 5,
    team_id: str | None = None,
    min_possessions: int = 1,
    sort_by: str = 'net_rating',
    sort_order: str = 'desc',
    player_id: str | None = None,
) -> list[LineupRecord]:
    """Return lineup summaries across the entire league.

    Iterates over every possession, generates all *n*-man lineup
    combinations (from the 5-player arrays stored on each possession),
    and aggregates counting stats on both offense and defense.  Derived
    analytics metrics are then computed for each unique lineup.

    Args:
        lineup_size: Number of players per lineup (1–5, default 5).
        team_id: Optional team UUID – only return lineups for this team.
        min_possessions: Minimum total possessions to include a lineup.
        sort_by: Response field to sort by (default ``net_rating``).
        sort_order: ``'asc'`` or ``'desc'`` (default ``'desc'``).
        player_id: Optional player UUID – only lineups containing this player.

    Returns:
        A list of ``LineupRecord`` dicts, each containing raw sums,
        derived metrics, and player/team metadata.
    """
    normalized_size = _normalize_lineup_size(lineup_size)

    # ── Build lookups ───────────────────────────────────────────────────
    player_map: dict[str, dict] = {}
    player_team_map: dict[str, str] = {}
    for p in Player.objects.select_related('team').all():
        pid = str(p.id)
        player_map[pid] = {'player_id': pid, 'name': p.name}
        player_team_map[pid] = str(p.team_id)

    team_map = {str(t.id): t.name for t in Team.objects.all()}

    # ── Aggregate possession stats by lineup ────────────────────────────
    lineup_data: dict[tuple[str, ...], dict] = {}

    for poss in Possession.objects.all().iterator():
        off_ids = sorted(str(uid) for uid in poss.offensive_player_ids)
        def_ids = sorted(str(uid) for uid in poss.defensive_player_ids)
        stat_vals = {f: getattr(poss, f) for f in AGGREGATION_FIELDS}
        poss_seconds = poss.seconds

        # Offensive combinations
        for combo in combinations(off_ids, normalized_size):
            entry = lineup_data.get(combo)
            if entry is None:
                entry = {
                    'off': defaultdict(float),
                    'def': defaultdict(float),
                    'off_poss': 0,
                    'def_poss': 0,
                    'off_seconds': 0.0,
                    'def_seconds': 0.0,
                }
                lineup_data[combo] = entry
            entry['off_poss'] += 1
            entry['off_seconds'] += poss_seconds
            off = entry['off']
            for f, v in stat_vals.items():
                off[f] += v

        # Defensive combinations
        for combo in combinations(def_ids, normalized_size):
            entry = lineup_data.get(combo)
            if entry is None:
                entry = {
                    'off': defaultdict(float),
                    'def': defaultdict(float),
                    'off_poss': 0,
                    'def_poss': 0,
                    'off_seconds': 0.0,
                    'def_seconds': 0.0,
                }
                lineup_data[combo] = entry
            entry['def_poss'] += 1
            entry['def_seconds'] += poss_seconds
            dfn = entry['def']
            for f, v in stat_vals.items():
                dfn[f] += v

    # ── Build response records ──────────────────────────────────────────
    results: list[LineupRecord] = []

    for combo, data in lineup_data.items():
        total_poss = data['off_poss'] + data['def_poss']
        if total_poss < min_possessions:
            continue

        # Derive team from the first player in the combo.
        lineup_team_id = player_team_map.get(combo[0], '')

        # Apply filters.
        if team_id and lineup_team_id != team_id:
            continue
        if player_id and player_id not in combo:
            continue

        record: LineupRecord = {
            'offensive_possessions': data['off_poss'],
            'defensive_possessions': data['def_poss'],
            'total_possessions': total_poss,
            'total_seconds': round(data['off_seconds'] + data['def_seconds'], 1),
        }

        # Raw aggregated stat sums.
        for f in AGGREGATION_FIELDS:
            record[f'offensive_{f}'] = int(data['off'][f])
            record[f'defensive_{f}'] = int(data['def'][f])

        _compute_derived_metrics(record)

        # Lineup metadata.
        record['team_id'] = lineup_team_id
        record['team_name'] = team_map.get(lineup_team_id, 'Unknown')
        record['player_ids'] = list(combo)
        record['players'] = [
            player_map.get(pid, {'player_id': pid, 'name': 'Unknown'})
            for pid in combo
        ]

        results.append(record)

    # ── Sort ────────────────────────────────────────────────────────────
    if results:
        reverse = sort_order != 'asc'
        try:
            results.sort(key=lambda r: (r.get(sort_by) is None, r.get(sort_by, 0)), reverse=reverse)
        except TypeError:
            results.sort(key=lambda r: r.get('total_possessions', 0), reverse=reverse)

    return results
