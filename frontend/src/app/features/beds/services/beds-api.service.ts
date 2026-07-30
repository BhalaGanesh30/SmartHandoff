/**
 * BedsApiService — fetches bed board data from the backend API.
 *
 * Maps mv_bed_board response to BedItem model including prediction fields (US-036).
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { BedItem } from '../models/bed.model';

interface BedApiResponse {
  bed_id: string;
  unit: string;
  room: string;
  bed_number: string;
  bed_status: string;
  encounter_id: string | null;
  last_updated: string;
  // US-036 prediction fields
  predicted_discharge_time: string | null;
  discharge_prediction_confidence: 'high' | 'medium' | 'low' | null;
  discharge_prediction_interval_hours: number | null;
}

@Injectable({
  providedIn: 'root',
})
export class BedsApiService {
  private readonly apiUrl = '/api/v1/beds';

  constructor(private http: HttpClient) {}

  getBedBoard(unit?: string): Observable<BedItem[]> {
    const url = unit ? `${this.apiUrl}?unit=${unit}` : this.apiUrl;
    return this.http.get<BedApiResponse[]>(url).pipe(
      map((response) => response.map(this.mapBedResponse))
    );
  }

  private mapBedResponse(raw: BedApiResponse): BedItem {
    return {
      bedId: raw.bed_id,
      unit: raw.unit,
      room: raw.room,
      bedNumber: raw.bed_number,
      bedStatus: raw.bed_status as BedItem['bedStatus'],
      encounterId: raw.encounter_id,
      lastUpdated: raw.last_updated,
      // US-036: Map prediction fields
      predictedDischargeTime: raw.predicted_discharge_time ?? null,
      dischargePredictionConfidence: raw.discharge_prediction_confidence ?? null,
      dischargePredictionIntervalHours: raw.discharge_prediction_interval_hours ?? null,
    };
  }
}
