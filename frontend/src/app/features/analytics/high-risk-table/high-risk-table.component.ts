/**
 * High-risk encounters table matching the SCR-009 wireframe.
 */
import { Component, Input } from '@angular/core';
import { NgIf, NgFor, DatePipe } from '@angular/common';

import { HighRiskEncountersResponse, HighRiskEncounter } from '../analytics.models';

@Component({
  selector: 'app-high-risk-table',
  standalone: true,
  imports: [NgIf, NgFor, DatePipe],
  template: `
    <div class="card">
      <div class="card-header">
        <h2>Top 10 High-Risk Encounters (Last 7 Days)</h2>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Patient (masked)</th>
              <th>Unit</th>
              <th>Risk Score</th>
              <th>Discharge Date</th>
              <th>Follow-up Status</th>
            </tr>
          </thead>
          <tbody>
            @if (encounters.length > 0) {
              @for (enc of encounters; track enc.masked_id + enc.discharge_date) {
                <tr>
                  <td>{{ enc.masked_id }}</td>
                  <td>{{ enc.unit ?? '—' }}</td>
                  <td>
                    <span class="risk-chip" [class]="chipClass(enc.risk_tier)">
                      {{ formatScore(enc.risk_score) }} {{ enc.risk_tier }}
                    </span>
                  </td>
                  <td>{{ enc.discharge_date ? (enc.discharge_date | date: 'yyyy-MM-dd') : '—' }}</td>
                  <td [class]="statusClass(enc.follow_up_status)">{{ enc.follow_up_status }}</td>
                </tr>
              }
            } @else {
              <tr>
                <td colspan="5" class="no-data-row">No high-risk encounters found for this period.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </div>
  `,
  styleUrl: './high-risk-table.component.scss',
})
export class HighRiskTableComponent {
  @Input() response: HighRiskEncountersResponse | null = null;

  get encounters(): HighRiskEncounter[] {
    return this.response?.encounters ?? [];
  }

  chipClass(tier: string): string {
    const map: Record<string, string> = {
      HIGH: 'high',
      MEDIUM: 'med',
      LOW: 'low',
    };
    return map[tier] ?? '';
  }

  statusClass(status: string): string {
    if (status.includes('✓')) return 'booked';
    if (status.includes('❌')) return 'missed';
    return 'pending';
  }

  formatScore(score: number | null): string {
    if (score === null) return '—';
    return score.toFixed(2);
  }
}
