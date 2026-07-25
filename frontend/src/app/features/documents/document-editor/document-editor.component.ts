/**
 * Document Editor Component (US-028 Scenario 2)
 * 
 * Provides editable interface for discharge summary sections with:
 * - 2-second debounced auto-save
 * - Client-side diff computation
 * - RBAC-controlled approve/reject buttons
 */
import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime, takeUntil } from 'rxjs/operators';
import { computeClientDiff, DiffResult } from '../utils/document-diff.util';

export interface SaveDraftPayload {
  diff: DiffResult;
  documentId: string;
}

@Component({
  selector: 'app-document-editor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="document-editor">
      <div class="editor-content">
        <textarea
          [(ngModel)]="editedContent"
          (ngModelChange)="onContentChange()"
        ></textarea>
      </div>
      
      <div class="actions">
        @if (canApprove) {
          <button
            class="approve-btn"
            aria-label="Approve document"
            (click)="onApprove()"
          >
            Approve
          </button>
        }
        
        <button
          class="reject-btn"
          aria-label="Reject document"
          (click)="onReject()"
        >
          Reject
        </button>
      </div>
    </div>
  `,
  styles: [`
    .document-editor {
      padding: 1rem;
    }
    
    .editor-content textarea {
      width: 100%;
      min-height: 300px;
    }
    
    .actions {
      margin-top: 1rem;
      display: flex;
      gap: 0.5rem;
    }
  `]
})
export class DocumentEditorComponent implements OnInit, OnDestroy {
  @Input() documentId: string = '';
  @Input() initialContent: Record<string, any> = {};
  @Input() aiDraft: Record<string, any> = {};
  @Input() userRole: string = '';
  
  @Output() saveDraft = new EventEmitter<SaveDraftPayload>();
  @Output() approve = new EventEmitter<void>();
  @Output() reject = new EventEmitter<void>();
  
  editedContent: string = '';
  currentSections: Record<string, any> = {};
  
  private contentChangeSubject = new Subject<void>();
  private destroy$ = new Subject<void>();
  
  get canApprove(): boolean {
    return this.userRole === 'physician' || this.userRole === 'admin';
  }
  
  ngOnInit(): void {
    this.currentSections = { ...this.aiDraft };
    
    // Set up debounced auto-save (2000ms)
    this.contentChangeSubject
      .pipe(
        debounceTime(2000),
        takeUntil(this.destroy$)
      )
      .subscribe(() => this.performAutoSave());
  }
  
  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
  
  onContentChange(): void {
    this.contentChangeSubject.next();
  }
  
  onSectionChange(field: string, value: any): void {
    this.currentSections[field] = value;
    this.contentChangeSubject.next();
  }
  
  private performAutoSave(): void {
    const diff = computeClientDiff(this.aiDraft, this.currentSections);
    
    // Only emit if there are actual changes
    if (Object.keys(diff).length > 0) {
      this.saveDraft.emit({
        diff,
        documentId: this.documentId
      });
    }
  }
  
  onApprove(): void {
    this.approve.emit();
  }
  
  onReject(): void {
    this.reject.emit();
  }
}
