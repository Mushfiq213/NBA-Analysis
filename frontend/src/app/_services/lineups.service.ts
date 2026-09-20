import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

import { BaseService } from './base.service';

export interface LineupQueryParams {
  lineup_size?: number;
  team_id?: string;
  min_possessions?: number;
  sort_by?: string;
  sort_order?: string;
  player_id?: string;
}

@Injectable({ providedIn: 'root' })
export class LineupsService extends BaseService {
  constructor(protected override http: HttpClient) {
    super(http);
  }

  private buildQueryParams(queryParams: Record<string, string | number>): HttpParams {
    return Object.entries(queryParams).reduce(
      (params, [key, value]) => params.set(key, String(value)),
      new HttpParams(),
    );
  }

  private buildDisplayedEndpointWithParams(
    endpoint: string,
    queryParams: Record<string, string | number>,
  ): string {
    const queryString = new URLSearchParams(
      Object.entries(queryParams).map(([key, value]) => [key, String(value)]),
    ).toString();
    return queryString ? `${endpoint}?${queryString}` : endpoint;
  }

  getLineupsLeagueSummary(paramsOrSize: LineupQueryParams | number = 5): Observable<{
    endpoint: string;
    apiResponse: unknown;
  }> {
    // Backward-compatible: accepts a plain number (lineup size) or a full params object.
    const params: LineupQueryParams =
      typeof paramsOrSize === 'number' ? { lineup_size: paramsOrSize } : paramsOrSize;

    const endpoint = `${this.baseUrl}/lineups`;
    const queryParams: Record<string, string | number> = {};

    if (params.lineup_size !== undefined) queryParams['lineup_size'] = params.lineup_size;
    if (params.team_id) queryParams['team_id'] = params.team_id;
    if (params.min_possessions !== undefined) queryParams['min_possessions'] = params.min_possessions;
    if (params.sort_by) queryParams['sort_by'] = params.sort_by;
    if (params.sort_order) queryParams['sort_order'] = params.sort_order;
    if (params.player_id) queryParams['player_id'] = params.player_id;

    const httpParams = this.buildQueryParams(queryParams);
    const displayedEndpointWithParams = this.buildDisplayedEndpointWithParams(endpoint, queryParams);

    return this.get(endpoint, httpParams).pipe(
      map((data) => ({
        endpoint: displayedEndpointWithParams,
        apiResponse: data,
      })),
    );
  }
}
