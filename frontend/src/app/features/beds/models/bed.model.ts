/**
 * Represents a single bed entry from the mv_bed_board API response.
 * Prediction fields are nullable (null when no admitted encounter or no prediction yet).
 *
 * Design refs:
 *   US-036 AC Scenario 4 — predicted_discharge_time + confidence_level on bed board
 *   US-036 Technical Notes — confidence tiers: 'high' | 'medium' | 'low'
 */

export type BedStatus = 'VACANT' | 'OCCUPIED' | 'DIRTY' | 'MAINTENANCE' | 'RESERVED';

export type ConfidenceLevel = 'high' | 'medium' | 'low' | null;

export interface BedItem {
  bedId: string;
  unit: string;
  room: string;
  bedNumber: string;
  bedStatus: BedStatus;
  encounterId: string | null;
  lastUpdated: string; // ISO datetime

  // US-036 prediction fields
  predictedDischargeTime: string | null;          // ISO datetime UTC
  dischargePredictionConfidence: ConfidenceLevel; // 'high' | 'medium' | 'low' | null
  dischargePredictionIntervalHours: number | null; // ±hours
}
