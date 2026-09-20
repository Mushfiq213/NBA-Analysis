import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginator, MatPaginatorModule } from '@angular/material/paginator';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSort, MatSortModule } from '@angular/material/sort';
import { MatTableDataSource, MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';

import { LineupQueryParams, LineupsService } from '../_services/lineups.service';

interface TeamOption {
  id: string;
  name: string;
}

interface LineupSizeOption {
  value: number;
  label: string;
}

@Component({
  selector: 'lineups-summary-component',
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSortModule,
    MatTableModule,
    MatTooltipModule,
  ],
  templateUrl: './lineups-summary.component.html',
  styleUrl: './lineups-summary.component.scss',
})
export class LineupsSummaryComponent implements OnInit, AfterViewInit {
  private readonly lineupsService = inject(LineupsService);
  private readonly cdr = inject(ChangeDetectorRef);

  private _sort?: MatSort;
  private _paginator?: MatPaginator;

  @ViewChild(MatSort)
  set sort(sort: MatSort | undefined) {
    if (sort) {
      this._sort = sort;
      this.dataSource.sort = sort;
      this.setupSorting();
    }
  }
  get sort(): MatSort | undefined {
    return this._sort;
  }

  @ViewChild(MatPaginator)
  set paginator(paginator: MatPaginator | undefined) {
    if (paginator) {
      this._paginator = paginator;
      this.dataSource.paginator = paginator;
    }
  }
  get paginator(): MatPaginator | undefined {
    return this._paginator;
  }

  readonly lineupSizes: LineupSizeOption[] = [
    { value: 5, label: '5-Man' },
    { value: 4, label: '4-Man' },
    { value: 3, label: '3-Man' },
    { value: 2, label: '2-Man' },
    { value: 1, label: '1-Man' },
  ];

  readonly displayedColumns = [
    'players',
    'team_name',
    'total_possessions',
    'offensive_rating',
    'defensive_rating',
    'net_rating',
    'offensive_efg_pct',
    'offensive_ts_pct',
    'offensive_tov_pct',
    'offensive_oreb_pct',
    'defensive_dreb_pct',
    'plus_minus',
  ];

  lineupSize = 5;
  selectedTeam = '';
  minPossessions = 1;
  teams: TeamOption[] = [];
  loading = false;
  totalLineups = 0;
  dataSource = new MatTableDataSource<any>([]);

  ngOnInit(): void {
    this.setupSorting();
    this.fetchData();
  }

  ngAfterViewInit(): void {
    if (this.sort) {
      this.dataSource.sort = this.sort;
    }
    if (this.paginator) {
      this.dataSource.paginator = this.paginator;
    }
    this.setupSorting();
    this.cdr.detectChanges();
  }

  onFilterChange(): void {
    if (this.paginator) {
      this.paginator.firstPage();
    }
    this.fetchData();
  }

  private setupSorting(): void {
    this.dataSource.sortingDataAccessor = (item: any, property: string): string | number => {
      if (property === 'players') {
        return (item.players?.map((p: any) => p.name).join(', ') ?? '').toLowerCase();
      }
      if (property === 'team_name') {
        return (item.team_name ?? '').toLowerCase();
      }
      const val = item[property];
      if (val === null || val === undefined) {
        return -Infinity;
      }
      const num = Number(val);
      return isNaN(num) ? String(val).toLowerCase() : num;
    };

    this.dataSource.sortData = (data: any[], sort: MatSort) => {
      const active = sort.active;
      const direction = sort.direction;
      if (!active || direction === '') {
        return data;
      }

      return data.slice().sort((a, b) => {
        const valueA = this.dataSource.sortingDataAccessor(a, active);
        const valueB = this.dataSource.sortingDataAccessor(b, active);

        let comparatorResult = 0;
        if (typeof valueA === 'number' && typeof valueB === 'number') {
          comparatorResult = valueA - valueB;
        } else {
          const strA = valueA != null ? String(valueA) : '';
          const strB = valueB != null ? String(valueB) : '';
          comparatorResult = strA.localeCompare(strB, undefined, { numeric: true, sensitivity: 'base' });
        }

        return comparatorResult * (direction === 'asc' ? 1 : -1);
      });
    };
  }

  // ── Formatting helpers ────────────────────────────────────────────────

  formatPct(value: number | null | undefined): string {
    if (value == null) return '—';
    return (value * 100).toFixed(1) + '%';
  }

  formatRating(value: number | null | undefined): string {
    if (value == null) return '—';
    return value.toFixed(1);
  }

  formatPlusMinus(value: number | null | undefined): string {
    if (value == null) return '—';
    return (value > 0 ? '+' : '') + value.toString();
  }

  getRatingClass(value: number): string {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
  }

  // ── Data fetching ─────────────────────────────────────────────────────

  private fetchData(): void {
    this.loading = true;
    const params: LineupQueryParams = {
      lineup_size: this.lineupSize,
      min_possessions: this.minPossessions,
    };
    if (this.selectedTeam) {
      params.team_id = this.selectedTeam;
    }

    this.lineupsService.getLineupsLeagueSummary(params).subscribe({
      next: (data) => {
        const rows = Array.isArray(data.apiResponse) ? (data.apiResponse as any[]) : [];
        this.dataSource.data = rows;
        this.totalLineups = rows.length;

        if (this.paginator) {
          this.dataSource.paginator = this.paginator;
          this.paginator.firstPage();
        }
        if (this.sort) {
          this.dataSource.sort = this.sort;
        }

        // Populate team filter from the first (unfiltered) response.
        if (this.teams.length === 0) {
          const teamMap = new Map<string, string>();
          for (const row of rows) {
            if (row.team_id && row.team_name) {
              teamMap.set(row.team_id, row.team_name);
            }
          }
          this.teams = Array.from(teamMap, ([id, name]) => ({ id, name })).sort((a, b) =>
            a.name.localeCompare(b.name),
          );
        }

        this.loading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.loading = false;
        this.dataSource.data = [];
        this.totalLineups = 0;
        this.cdr.detectChanges();
      },
    });
  }
}
