import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';

import { KpiDataPoint } from '../analytics.models';
import { toDateLabels } from './chart.utils';

interface VolumePoint {
  label: string;
  value: number;
  y: number;
}

@Component({
  selector: 'app-discharge-volume-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './discharge-volume-chart.component.html',
  styleUrl: './discharge-volume-chart.component.scss',
})
export class DischargeVolumeChartComponent implements OnChanges {
  @Input() data: KpiDataPoint[] = [];

  points: VolumePoint[] = [];
  polylinePoints = '';
  areaPoints = '';
  maxValue = 0;
  labelPositions: { label: string; x: number }[] = [];

  ngOnChanges(): void {
    const labels = toDateLabels(this.data);
    this.points = this.data.map((d, i) => ({
      label: labels[i] ?? '',
      value: d.discharge_volume ?? 0,
      y: 0,
    }));

    const values = this.points.map((p) => p.value);
    this.maxValue = Math.max(...values, 1);

    const width = 400;
    const height = 120;
    const stepX = this.points.length > 1 ? width / (this.points.length - 1) : 0;

    this.points = this.points.map((p, i) => {
      const x = stepX * i;
      const y = height - (p.value / this.maxValue) * (height - 10) - 5;
      return { ...p, y };
    });

    const linePoints = this.points.map((p, i) => `${stepX * i},${p.y}`).join(' ');
    this.polylinePoints = linePoints;
    this.areaPoints = `${linePoints} ${width},${height} 0,${height}`;

    this.labelPositions = this.points
      .filter((_, i) => i % Math.max(1, Math.floor(this.points.length / 5)) === 0)
      .map((p, i, arr) => ({
        label: p.label,
        x: (400 / (arr.length - 1 || 1)) * i,
      }));
  }
}
