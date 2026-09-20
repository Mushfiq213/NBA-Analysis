# -*- coding: utf-8 -*-
import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from app.helpers.lineups import get_lineup_league_summary_stats

LOGGER = logging.getLogger('django')


def _parse_int_query_param(request, key, default, minimum=None, maximum=None):
    """Parse an int query param with optional bounds."""
    raw_value = request.query_params.get(key, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _get_lineup_query_options(request):
    """Extract and validate all query parameters for lineup queries."""
    sort_order_raw = request.query_params.get('sort_order', 'desc')
    sort_order = sort_order_raw if sort_order_raw in ('asc', 'desc') else 'desc'

    team_id_raw = request.query_params.get('team_id', None)
    player_id_raw = request.query_params.get('player_id', None)

    return {
        'lineup_size': _parse_int_query_param(
            request, key='lineup_size', default=5, minimum=1, maximum=5,
        ),
        'min_possessions': _parse_int_query_param(
            request, key='min_possessions', default=1, minimum=1,
        ),
        'sort_by': request.query_params.get('sort_by', 'net_rating'),
        'sort_order': sort_order,
        'team_id': team_id_raw if team_id_raw else None,
        'player_id': player_id_raw if player_id_raw else None,
    }


class LineupsLeagueSummary(APIView):
    logger = LOGGER

    def get(self, request):
        """Return the league-wide lineup summary."""
        query_options = _get_lineup_query_options(request)
        return Response(get_lineup_league_summary_stats(**query_options))
