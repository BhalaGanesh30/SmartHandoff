import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';

import { RiskDistributionResponse, RiskDistributionBucket } from '../analytics.models';

interface DonutSegment {
  tier: string;
  dasharray: string;
  transform: string;
  color: string;
}

@Component({
  selector: 'app-risk-distribution-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './risk-distribution-chart.component.html',
  styleUrl: './risk-distribution-chart.component.scss',
})
export class RiskDistributionChartComponent implements OnChanges {
  @Input() riskDistribution: RiskDistributionResponse | null = null;

  buckets: RiskDistributionBucket[] = [];
  segments: DonutSegment[] = [];
  total = 0;

  private readonly colors: Record<string, string> = {
    LOW: '#16A34A',
    MEDIUM: '#D97706',
    HIGH: '#DC2626',
    ['UNKNOWN']: '#9CA3AF',
  };

  private readonly labels: Record<string, string> = {
    LOW: 'Low risk (<0.3)',
    MEDIUM: 'Medium (0.3–0.7)',
    HIGH: 'High risk (>0.7)',
    ['UNKNOWN']: 'Unknown',
  };

  get hasData(): boolean {
    return this.buckets.length > 0 && this.buckets.some((b) => b.count > 0);
  }

  ngOnChanges(): void {
    this.buckets = this.riskDistribution?.buckets ?? [];
    this.total = this.riskDistribution?.total ?? 0;
    this.segments = this._buildSegments(this.buckets);
  }

  colorFor(tier: string): string {
    return this.colors[tier] ?? this.colors['UNKNOWN'];
  }

  labelFor(tier: string): string {
    return this.labels[tier] ?? tier;
  }

  private _buildSegments(buckets: RiskDistributionBucket[]): DonutSegment[] {
    const ordered = this._orderBuckets(buckets);
    let cumulative = 0;
    return ordered.map((b) => {
      const segment = {
        tier: b.tier,
        dasharray: `${b.percentage} ${100 - b.percentage}`,
        transform: `rotate(${-90 + cumulative * 3.6} 18 18)`,
        color: this.colorFor(b.tier),
      };
      cumulative += b.percentage;
      return segment;
    });
  }

  private _orderBuckets(buckets: RiskDistributionBucket[]): RiskDistributionBucket[] {
    const order = { LOW: 0, MEDIUM: 1, HIGH: 2, UNKNOWN: 3 };
    return [...buckets].sort((a, b) => (order[a.tier as keyof typeof order] ?? 99) - (order[b.tier as keyof typeof order] ?? 99));
  }
}
