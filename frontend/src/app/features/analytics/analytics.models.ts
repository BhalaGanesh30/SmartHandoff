/**
 * Client-side models matching the KpiResponse / KpiDataPoint Pydantic schemas
 * returned by GET /api/v1/analytics/kpis.
 *
 * IMPORTANT — PHI guardrail:
 *   No PHI fields are modelled here. All fields are aggregated metrics only.
 *   See US-061 AC Scenario 3.
 */

export interface KpiDataPoint {
  /** ISO 8601 date string — e.g. "2026-07-01" */
  date: string;
  unit: string;
  avg_discharge_doc_time_min: number | null;
  readmission_rate_30d: number | null;
  med_recon_completion_rate: number | null;
  bed_utilisation_pct: number | null;
  agent_task_success_rate: number | null;
  discharge_volume: number | null;
}

export interface KpiResponse {
  from_date: string;
  to_date: string;
  unit: string | null;
  data: KpiDataPoint[];
  total_rows: number;
}

/** Filter parameters sent as URL query params to the API and reflected in the browser URL. */
export interface KpiFilterParams {
  from: string;   // ISO 8601 date
  to: string;     // ISO 8601 date
  unit?: string;
}

/** Readmission risk tier distribution bucket. */
export interface RiskDistributionBucket {
  tier: string;
  count: number;
  percentage: number;
}

/** Risk distribution response from /api/v1/analytics/risk-distribution. */
export interface RiskDistributionResponse {
  from_date: string;
  to_date: string;
  unit: string | null;
  buckets: RiskDistributionBucket[];
  total: number;
}

/** De-identified high-risk encounter row. */
export interface HighRiskEncounter {
  masked_id: string;
  unit: string | null;
  risk_score: number | null;
  risk_tier: string;
  discharge_date: string | null;
  follow_up_status: string;
}

/** High-risk encounters response from /api/v1/analytics/high-risk-encounters. */
export interface HighRiskEncountersResponse {
  from_date: string;
  to_date: string;
  unit: string | null;
  encounters: HighRiskEncounter[];
  total: number;
}
