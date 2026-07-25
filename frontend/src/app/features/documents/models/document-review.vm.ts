/** View model for DocumentReviewComponent — maps API Document to UI state. */
export interface DocumentReviewVm {
  id: string;
  status: 'DRAFT' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';
  aiDraftHtml: string;        // Pre-sanitised HTML of the immutable AI draft
  aiDraftContent: Record<string, string>;  // Structured sections of AI draft
  content: Record<string, string>;         // Current editable content (may differ from draft)
  isAiAssisted: boolean;
  encounterId: string;
  
  /** US-029: Permanent AI provenance flag. Always true for agent-generated docs. */
  ai_assisted_label: boolean;
  
  /** US-029: UTC ISO string of clinician approval; null until approved. */
  approved_at: string | null;
  
  /** US-029: Resolved display name of the approving clinician (for footer). */
  reviewed_by_display_name: string | null;
}
