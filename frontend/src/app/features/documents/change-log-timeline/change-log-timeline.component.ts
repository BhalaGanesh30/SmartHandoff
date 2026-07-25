/**
 * ChangeLogTimelineComponent
 *
 * Displays the chronological change audit trail below the editable pane (US-028 DoD item 4).
 * Loads from GET /api/v1/documents/{id}/change-log on init and refreshes
 * whenever a new saveDraft completes (via SignalR or polling — Phase 2).
 */
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  OnInit,
  inject,
} from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { Observable } from 'rxjs';

import { DocumentService } from '../services/document.service';
import { ChangeLogEntry } from '../models/change-log-entry.model';

@Component({
  selector: 'sh-change-log-timeline',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, DatePipe, MatExpansionModule, MatIconModule],
  templateUrl: './change-log-timeline.component.html',
  styleUrl: './change-log-timeline.component.scss',
})
export class ChangeLogTimelineComponent implements OnInit {
  @Input({ required: true }) documentId!: string;

  private readonly documentService = inject(DocumentService);

  changeLog$!: Observable<ChangeLogEntry[]>;

  ngOnInit(): void {
    this.changeLog$ = this.documentService.getChangeLog(this.documentId);
  }
}
