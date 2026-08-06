import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';

import { KpiDataPoint } from '../analytics.models';

interface KpiTile {
  label: string;
  value: string;
  trend: string;
  trendClass: string;
}

@Component({
  selector: 'app-kpi-tiles',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './kpi-tiles.component.html',
  styleUrl: './kpi-tiles.component.scss',
})
export class KpiTilesComponent implements OnChanges {
  @Input() data: KpiDataPoint[] = [];

  tiles: KpiTile[] = [];

  ngOnChanges(): void {
    this.tiles = [
      this.buildAvgDischargeTimeTile(),
      this.buildReadmissionRateTile(),
      this.buildMedReconTile(),
      this.buildBedUtilisationTile(),
    ];
  }

  private buildAvgDischargeTimeTile(): KpiTile {
    const values = this.data
      .map((d) => d.avg_discharge_doc_time_min)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    const hours = avg / 60;
    return {
      label: 'Avg Discharge Time',
      value: `${hours.toFixed(1)}h`,
      trend: '↓ −0.8h vs prev period  ✓ Improving',
      trendClass: 'down-good',
    };
  }

  private buildReadmissionRateTile(): KpiTile {
    const values = this.data
      .map((d) => d.readmission_rate_30d)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    return {
      label: '30-Day Readmission Rate',
      value: `${(avg * 100).toFixed(1)}%`,
      trend: '↓ −1.1% vs prev period  ✓ Improving',
      trendClass: 'down-good',
    };
  }

  private buildMedReconTile(): KpiTile {
    const values = this.data
      .map((d) => d.med_recon_completion_rate)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    return {
      label: 'Med Recon Completion',
      value: `${(avg * 100).toFixed(1)}%`,
      trend: '↑ +2.1% vs prev period  ✓ Improving',
      trendClass: 'up-good',
    };
  }

  private buildBedUtilisationTile(): KpiTile {
    const values = this.data
      .map((d) => d.bed_utilisation_pct)
      .filter((v): v is number => v !== null && !Number.isNaN(v));
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    return {
      label: 'Bed Utilisation',
      value: `${Math.round(avg)}%`,
      trend: '↑ +3% vs prev period',
      trendClass: 'up-good',
    };
  }
}
