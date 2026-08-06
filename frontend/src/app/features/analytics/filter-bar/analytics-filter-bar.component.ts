/**
 * Standalone filter bar for the analytics dashboard.
 *
 * Inputs:
 *   initialFilters — current filter state (from URL query params or defaults)
 *   availableUnits — unit options from app_user.units (JWT claims)
 *
 * Outputs:
 *   filterChange — emits KpiFilterParams when the manager submits new filter values
 *
 * Design refs:
 *   US-061 DoD — MatDateRangePicker; unit dropdown; URL query params
 *   US-061 AC Scenario 1 — pre-set to last 30 days
 *   US-061 AC Scenario 2 — simultaneous chart update on filter apply
 */
import { NgIf } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { KpiFilterParams } from '../analytics.models';

@Component({
  selector: 'app-analytics-filter-bar',
  standalone: true,
  imports: [NgIf, ReactiveFormsModule],
  templateUrl: './analytics-filter-bar.component.html',
  styleUrl: './analytics-filter-bar.component.scss',
})
export class AnalyticsFilterBarComponent implements OnInit {
  @Input() initialFilters!: KpiFilterParams;
  /** Units the manager can access — derived from app_user.units in the JWT. */
  @Input() availableUnits: string[] = [];

  @Output() filterChange = new EventEmitter<KpiFilterParams>();

  private readonly fb = inject(FormBuilder);

  filterForm!: FormGroup;
  showCustomDateRange = false;

  ngOnInit(): void {
    const startDate = this.parseDate(this.initialFilters.from);
    const endDate = this.parseDate(this.initialFilters.to);
    const preset = this._detectPreset(startDate, endDate);

    this.filterForm = this.fb.group({
      dateRangePreset: [preset],
      dateRange: this.fb.group({
        start: [startDate, Validators.required],
        end: [endDate, Validators.required],
      }),
      unit: [this.initialFilters.unit ?? null],
    });

    this.showCustomDateRange = preset === 'custom';

    this.filterForm.valueChanges.subscribe(() => {
      this.applyFilter();
    });
  }

  /** Called when the preset dropdown changes. */
  onPresetChange(): void {
    const preset = this.filterForm.value.dateRangePreset;
    if (preset === 'custom') {
      this.showCustomDateRange = true;
      return;
    }

    this.showCustomDateRange = false;
    const days = parseInt(preset, 10);
    const today = new Date();
    const from = new Date(today);
    from.setDate(today.getDate() - days);

    this.filterForm.patchValue({
      dateRange: { start: from, end: today },
    }, { emitEvent: false });

    this.applyFilter();
  }

  /** Emit the current filter values as KpiFilterParams. */
  applyFilter(): void {
    if (this.filterForm.invalid) return;

    const { dateRange, unit } = this.filterForm.value;
    const filters: KpiFilterParams = {
      from: this.formatDate(dateRange.start),
      to: this.formatDate(dateRange.end),
      unit: unit ?? undefined,
    };
    this.filterChange.emit(filters);
  }

  private parseDate(iso: string): Date {
    return new Date(iso);
  }

  private formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
  }

  private _detectPreset(from: Date, to: Date): string {
    const diffTime = to.getTime() - from.getTime();
    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
    if (diffDays === 7) return '7';
    if (diffDays === 30) return '30';
    if (diffDays === 90) return '90';
    return 'custom';
  }
}
