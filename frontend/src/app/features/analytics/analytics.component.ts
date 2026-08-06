/**
 * Top-level shell component for the /analytics route.
 *
 * Responsibilities at this layer (shell only):
 *   - Inject AnalyticsApiService and ActivatedRoute
 *   - Initialise filter params from URL query params (or defaults)
 *   - Expose a KpiResponse$ observable for child chart components to consume
 *   - Populate availableUnits from the current user's JWT claims
 *   - Handle CSV and PDF export actions
 *
 * Filter bar (TASK-004) and chart components (TASK-005) will be composed into
 * the template of this shell.
 *
 * Design refs:
 *   design.md §3.4 — features/analytics/ module
 *   US-061 DoD — AnalyticsComponent Angular lazy-loaded module
 *   US-056 TASK-005 — AuthService in-memory JWT storage
 *   US-063 — Export CSV/PDF from analytics dashboard
 */
import { AsyncPipe, NgIf, NgFor, DecimalPipe } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, map, switchMap } from 'rxjs';

import { AuthService } from '@core/auth/auth.service';
import { AnalyticsApiService } from './analytics-api.service';
import { AnalyticsExportService } from './services/analytics-export.service';
import { AnalyticsFilterBarComponent } from './filter-bar/analytics-filter-bar.component';
import { DischargeVolumeChartComponent } from './charts/discharge-volume-chart.component';
import { RiskDistributionChartComponent } from './charts/risk-distribution-chart.component';
import { HighRiskTableComponent } from './high-risk-table/high-risk-table.component';
import {
  KpiFilterParams,
  KpiResponse,
  RiskDistributionResponse,
  HighRiskEncountersResponse,
} from './analytics.models';

export interface KpiTileData {
  label: string;
  value: string;
  trend: string;
  trendClass: string;
}

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    AsyncPipe,
    NgIf,
    NgFor,
    DecimalPipe,
    AnalyticsFilterBarComponent,
    DischargeVolumeChartComponent,
    RiskDistributionChartComponent,
    HighRiskTableComponent,
  ],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
})
export class AnalyticsComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly apiService = inject(AnalyticsApiService);
  private readonly exportService = inject(AnalyticsExportService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  kpiData$!: Observable<KpiResponse>;
  kpiTiles$!: Observable<KpiTileData[]>;
  riskDistribution$!: Observable<RiskDistributionResponse>;
  highRiskEncounters$!: Observable<HighRiskEncountersResponse>;
  initialFilters!: KpiFilterParams;
  availableUnits: string[] = [];

  isExportingCsv = false;
  isExportingPdf = false;
  exportError: string | null = null;

  ngOnInit(): void {
    // Initialise filters from defaults
    const defaults = this.apiService.defaultFilters();
    this.initialFilters = {
      from: this.route.snapshot.queryParams['from'] ?? defaults.from,
      to: this.route.snapshot.queryParams['to'] ?? defaults.to,
      unit: this.route.snapshot.queryParams['unit'] ?? undefined,
    };

    // Populate available units from the current user's JWT claims (manager's accessible units).
    this.availableUnits = this.authService.currentUser()?.units ?? [];

    const filters$ = this.route.queryParams.pipe(
      map((params) => ({
        from: params['from'] ?? defaults.from,
        to: params['to'] ?? defaults.to,
        unit: params['unit'] ?? undefined,
      })),
    );

    this.kpiData$ = filters$.pipe(switchMap((filters) => this.apiService.getKpis(filters)));
    this.riskDistribution$ = filters$.pipe(
      switchMap((filters) => this.apiService.getRiskDistribution(filters)),
    );
    this.highRiskEncounters$ = filters$.pipe(
      switchMap((filters) => this.apiService.getHighRiskEncounters(filters, 10)),
    );

    this.kpiTiles$ = this.kpiData$.pipe(map((response) => this._buildTiles(response)));
  }

  private _buildTiles(response: KpiResponse): KpiTileData[] {
    const data = response.data ?? [];
    const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const half = Math.floor(sorted.length / 2);
    const prev = sorted.slice(0, half);
    const curr = sorted.slice(half);

    const avg = (arr: typeof data, field: keyof typeof data[0]): number | null => {
      const values = arr
        .map((d) => d[field])
        .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v));
      return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
    };

    const trend = (currAvg: number | null, prevAvg: number | null, lowerIsBetter = false): KpiTileData['trend'] => {
      if (currAvg === null || prevAvg === null || prevAvg === 0) {
        return '— No change vs prev period';
      }
      const delta = currAvg - prevAvg;
      const sign = delta >= 0 ? '↑' : '↓';
      const isGood = lowerIsBetter ? delta < 0 : delta > 0;
      return `${sign} ${Math.abs(delta).toFixed(1)} vs prev period${isGood ? '  ✓ Improving' : ''}`;
    };

    const trendClass = (delta: number | null, lowerIsBetter = false): string => {
      if (delta === null) return 'neutral';
      const isGood = lowerIsBetter ? delta < 0 : delta > 0;
      return isGood ? 'up-good' : 'up-bad';
    };

    const dischargeMin = avg(curr, 'avg_discharge_doc_time_min');
    const prevDischarge = avg(prev, 'avg_discharge_doc_time_min');
    const dischargeDelta = dischargeMin !== null && prevDischarge !== null ? dischargeMin - prevDischarge : null;

    const readmitRate = avg(curr, 'readmission_rate_30d');
    const prevReadmit = avg(prev, 'readmission_rate_30d');
    const readmitDelta = readmitRate !== null && prevReadmit !== null ? readmitRate - prevReadmit : null;

    const medRecon = avg(curr, 'med_recon_completion_rate');
    const prevMedRecon = avg(prev, 'med_recon_completion_rate');
    const medReconDelta = medRecon !== null && prevMedRecon !== null ? medRecon - prevMedRecon : null;

    const bedUtil = avg(curr, 'bed_utilisation_pct');
    const prevBedUtil = avg(prev, 'bed_utilisation_pct');
    const bedUtilDelta = bedUtil !== null && prevBedUtil !== null ? bedUtil - prevBedUtil : null;

    return [
      {
        label: 'Avg Discharge Time',
        value: dischargeMin !== null ? `${dischargeMin.toFixed(1)}h` : '—',
        trend: trend(dischargeMin, prevDischarge, true),
        trendClass: trendClass(dischargeDelta, true),
      },
      {
        label: '30-Day Readmission Rate',
        value: readmitRate !== null ? `${(readmitRate * 100).toFixed(1)}%` : '—',
        trend: trend(readmitRate, prevReadmit, true),
        trendClass: trendClass(readmitDelta, true),
      },
      {
        label: 'Med Recon Completion',
        value: medRecon !== null ? `${(medRecon * 100).toFixed(1)}%` : '—',
        trend: trend(medRecon, prevMedRecon),
        trendClass: trendClass(medReconDelta),
      },
      {
        label: 'Bed Utilisation',
        value: bedUtil !== null ? `${Math.round(bedUtil)}%` : '—',
        trend: trend(bedUtil, prevBedUtil),
        trendClass: trendClass(bedUtilDelta),
      },
    ];
  }

  /**
   * Called by the filter bar when the manager changes the date range or unit.
   * Updates URL query params, which triggers all data streams to re-fetch.
   */
  onFilterChange(filters: KpiFilterParams): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        from: filters.from,
        to: filters.to,
        unit: filters.unit ?? null,
      },
      queryParamsHandling: 'merge',
    });
  }

  onExportCsv(): void {
    this.isExportingCsv = true;
    this.exportError = null;
    this.exportService
      .downloadCsv(this.initialFilters.from, this.initialFilters.to)
      .subscribe({
        next: () => (this.isExportingCsv = false),
        error: (err) => {
          this.isExportingCsv = false;
          this.exportError = 'CSV export failed. Please try again.';
          console.error('[AnalyticsDashboard] CSV export error:', err);
        },
      });
  }

  onExportPdf(): void {
    this.isExportingPdf = true;
    this.exportError = null;
    this.exportService
      .initiatePdfExport(this.initialFilters.from, this.initialFilters.to)
      .subscribe({
        next: () => (this.isExportingPdf = false),
        error: (err) => {
          this.isExportingPdf = false;
          this.exportError = 'PDF export failed or timed out. Please try again.';
          console.error('[AnalyticsDashboard] PDF export error:', err);
        },
      });
  }
}


