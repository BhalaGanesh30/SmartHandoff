/**
 * Service for fetching KPI analytics data from the backend.
 *
 * Design refs:
 *   design.md §3.3 — GET /api/v1/analytics/kpis
 *   US-061 Technical Notes — query params: from, to, unit
 *   US-061 AC Scenario 1 — default 30-day range
 *   US-061 AC Scenario 2 — filter updates reflected within 2 s
 */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  HighRiskEncountersResponse,
  KpiFilterParams,
  KpiResponse,
  RiskDistributionResponse,
} from './analytics.models';

@Injectable({ providedIn: 'root' })
export class AnalyticsApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/api/v1/analytics`;

  /**
   * Fetch KPI data for the given filter parameters.
   * All three params are forwarded as URL query strings.
   * The JWT is attached automatically by the JwtInterceptor (core/auth).
   */
  getKpis(filters: KpiFilterParams): Observable<KpiResponse> {
    const params = this._buildParams(filters);
    return this.http.get<KpiResponse>(`${this.baseUrl}/kpis`, { params });
  }

  /**
   * Fetch readmission risk tier distribution for the donut chart.
   */
  getRiskDistribution(filters: KpiFilterParams): Observable<RiskDistributionResponse> {
    const params = this._buildParams(filters);
    return this.http.get<RiskDistributionResponse>(`${this.baseUrl}/risk-distribution`, { params });
  }

  /**
   * Fetch top high-risk discharged encounters for the table.
   */
  getHighRiskEncounters(filters: KpiFilterParams, limit = 10): Observable<HighRiskEncountersResponse> {
    const params = this._buildParams(filters).set('limit', limit.toString());
    return this.http.get<HighRiskEncountersResponse>(`${this.baseUrl}/high-risk-encounters`, { params });
  }

  /**
   * Return default filter params: last 30 days, no unit filter.
   * Used to initialise the filter form and URL query params on first load.
   */
  defaultFilters(): KpiFilterParams {
    const today = new Date();
    const from = new Date(today);
    from.setDate(today.getDate() - 30);

    return {
      from: from.toISOString().split('T')[0],
      to: today.toISOString().split('T')[0],
    };
  }

  private _buildParams(filters: KpiFilterParams): HttpParams {
    let params = new HttpParams()
      .set('from', filters.from)
      .set('to', filters.to);

    if (filters.unit) {
      params = params.set('unit', filters.unit);
    }

    return params;
  }
}
