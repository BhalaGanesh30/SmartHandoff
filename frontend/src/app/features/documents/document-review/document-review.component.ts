/**
 * DocumentReviewComponent
 *
 * Dual-pane document review UI (US-028 Scenario 1).
 * Left pane: read-only AI draft.  Right pane: editable copy with auto-save.
 * Both panes scroll in sync via ElementRef scroll event listeners.
 */
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import {
  Subject,
  debounceTime,
  distinctUntilChanged,
  fromEvent,
  switchMap,
  takeUntil,
} from 'rxjs';

import { DocumentService } from '../services/document.service';
import { DocumentEditorComponent } from '../document-editor/document-editor.component';
import { ChangeLogTimelineComponent } from '../change-log-timeline/change-log-timeline.component';
import { DocumentReviewVm } from '../models/document-review.vm';
import { AiAssistedLabelBannerComponent } from '../components/ai-assisted-label-banner/ai-assisted-label-banner.component';

@Component({
  selector: 'sh-document-review',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    DocumentEditorComponent,
    ChangeLogTimelineComponent,
    AiAssistedLabelBannerComponent,
  ],
  templateUrl: './document-review.component.html',
  styleUrl: './document-review.component.scss',
})
export class DocumentReviewComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('leftPane') leftPane!: ElementRef<HTMLDivElement>;
  @ViewChild('rightPane') rightPane!: ElementRef<HTMLDivElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly documentService = inject(DocumentService);
  private readonly destroy$ = new Subject<void>();

  documentId!: string;
  vm: DocumentReviewVm | null = null;
  isSaving = false;

  /** Prevents scroll-sync feedback loop between the two panes. */
  private isScrollSyncing = false;

  ngOnInit(): void {
    this.documentId = this.route.snapshot.paramMap.get('id')!;
    this.documentService
      .getDocument(this.documentId)
      .pipe(takeUntil(this.destroy$))
      .subscribe((doc) => (this.vm = doc));
  }

  ngAfterViewInit(): void {
    this.initScrollSync(this.leftPane, this.rightPane);
    this.initScrollSync(this.rightPane, this.leftPane);
  }

  /**
   * Mirror scroll position from `source` to `target`.
   * Debounced at 16 ms (≈ 60 fps) to avoid jank.
   * Guard flag prevents the mirrored scroll from triggering a second sync.
   */
  private initScrollSync(
    source: ElementRef<HTMLDivElement>,
    target: ElementRef<HTMLDivElement>,
  ): void {
    fromEvent(source.nativeElement, 'scroll')
      .pipe(debounceTime(16), takeUntil(this.destroy$))
      .subscribe(() => {
        if (this.isScrollSyncing) return;
        this.isScrollSyncing = true;
        target.nativeElement.scrollTop = source.nativeElement.scrollTop;
        // Reset flag after browser repaints
        requestAnimationFrame(() => (this.isScrollSyncing = false));
      });
  }

  onSaveDraft(payload: { content: Record<string, unknown>; diff: Record<string, unknown> }): void {
    if (!this.documentId) return;
    this.isSaving = true;
    this.documentService
      .saveDraft(this.documentId, payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => (this.isSaving = false),
        error: () => (this.isSaving = false),
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
