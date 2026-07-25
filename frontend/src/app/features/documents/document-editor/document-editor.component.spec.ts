/**
 * Unit tests for DocumentEditorComponent auto-save debounce (US-028 Scenario 2).
 */
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { DocumentEditorComponent } from './document-editor.component';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

describe('DocumentEditorComponent — auto-save', () => {
  let component: DocumentEditorComponent;
  let fixture: ComponentFixture<DocumentEditorComponent>;
  let saveDraftSpy: jest.SpyInstance;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DocumentEditorComponent, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(DocumentEditorComponent);
    component = fixture.componentInstance;
    component.documentId = 'doc-123';
    component.initialContent = { medications: 'Aspirin' };
    component.aiDraft = { medications: 'Aspirin' };
    component.userRole = 'nurse';
    fixture.detectChanges();

    saveDraftSpy = jest.spyOn(component.saveDraft, 'emit');
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('does NOT emit saveDraft immediately on content change', fakeAsync(() => {
    component.onSectionChange('medications', 'Warfarin');
    tick(1000); // Less than debounce window
    expect(saveDraftSpy).not.toHaveBeenCalled();
  }));

  it('emits saveDraft after 2000ms debounce', fakeAsync(() => {
    component.onSectionChange('medications', 'Warfarin');
    tick(2000);
    expect(saveDraftSpy).toHaveBeenCalledTimes(1);
    const payload = saveDraftSpy.mock.calls[0][0];
    expect(payload.diff['medications']).toBeDefined();
  }));

  it('does NOT emit saveDraft when diff is empty (no change from AI draft)', fakeAsync(() => {
    component.onSectionChange('medications', 'Aspirin'); // Same as aiDraft
    tick(2000);
    expect(saveDraftSpy).not.toHaveBeenCalled();
  }));

  it('Approve button is NOT rendered for nurse role', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const approveBtn = compiled.querySelector('[aria-label="Approve document"]');
    expect(approveBtn).toBeNull();
  });

  it('Reject button IS rendered for nurse role', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const rejectBtn = compiled.querySelector('[aria-label="Reject document"]');
    expect(rejectBtn).not.toBeNull();
  });

  it('Approve button IS rendered for physician role', () => {
    component.userRole = 'physician';
    fixture.detectChanges();
    
    const compiled = fixture.nativeElement as HTMLElement;
    const approveBtn = compiled.querySelector('[aria-label="Approve document"]');
    expect(approveBtn).not.toBeNull();
  });

  it('debounces multiple rapid changes', fakeAsync(() => {
    component.onSectionChange('medications', 'Change 1');
    tick(500);
    component.onSectionChange('medications', 'Change 2');
    tick(500);
    component.onSectionChange('medications', 'Final change');
    tick(2000);
    
    // Only the final change should trigger a save
    expect(saveDraftSpy).toHaveBeenCalledTimes(1);
  }));

  it('includes document ID in save payload', fakeAsync(() => {
    component.onSectionChange('medications', 'Warfarin');
    tick(2000);
    
    const payload = saveDraftSpy.mock.calls[0][0];
    expect(payload.documentId).toBe('doc-123');
  }));
});
