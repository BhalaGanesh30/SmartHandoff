/**
 * DocumentService
 *
 * Angular service encapsulating all Document API calls for the review workflow.
 *
 * - saveDraft: PATCH /api/v1/documents/{id}
 * - approveDocument: PATCH /api/v1/documents/{id}/approve
 * - rejectDocument: PATCH /api/v1/documents/{id}/reject
 * - getChangeLog: GET /api/v1/documents/{id}/change-log
 * - getDocument: GET /api/v1/documents/{id}
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { DocumentReviewVm } from '../models/document-review.vm';
import { ChangeLogEntry } from '../models/change-log-entry.model';

/** Payload for auto-save draft endpoint. */
export interface SaveDraftPayload {
  content: Record<string, unknown>;
  diff: Record<string, {
    old_value: unknown;
    new_value: unknown;
  }>;
}

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/api/v1/documents`;

  /** Load document for dual-pane review. */
  getDocument(documentId: string): Observable<DocumentReviewVm> {
    return this.http.get<DocumentReviewVm>(`${this.base}/${documentId}`);
  }

  /**
   * Auto-save edited content and append change log entries.
   * Called by DocumentEditorComponent after 2-second debounce.
   */
  saveDraft(
    documentId: string,
    payload: SaveDraftPayload,
  ): Observable<{ document_id: string; status: string; changes_recorded: number }> {
    return this.http.patch<{ document_id: string; status: string; changes_recorded: number }>(
      `${this.base}/${documentId}`,
      payload,
    );
  }

  /**
   * Approve document — physician role only.
   * Backend returns 403 for non-physician callers.
   */
  approveDocument(
    documentId: string,
    body: { notes?: string },
  ): Observable<{ document_id: string; status: string }> {
    return this.http.patch<{ document_id: string; status: string }>(
      `${this.base}/${documentId}/approve`,
      body,
    );
  }

  /**
   * Reject document — all reviewer roles.
   * `rejection_reason` is mandatory (min 10 characters validated by backend).
   */
  rejectDocument(
    documentId: string,
    body: { rejection_reason: string },
  ): Observable<{ document_id: string; status: string }> {
    return this.http.patch<{ document_id: string; status: string }>(
      `${this.base}/${documentId}/reject`,
      body,
    );
  }

  /** Fetch paginated change log with author display names. */
  getChangeLog(documentId: string): Observable<ChangeLogEntry[]> {
    return this.http.get<ChangeLogEntry[]>(`${this.base}/${documentId}/change-log`);
  }
}
