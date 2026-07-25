/**
 * Unit tests for AiAssistedLabelBannerComponent.
 *
 * Validates US-029 Scenario 1 (banner visible) and Scenario 2 (banner absent,
 * approved footer shown) label visibility logic.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import {
  AiAssistedLabelBannerComponent,
  DocumentStatus,
} from './ai-assisted-label-banner.component';

describe('AiAssistedLabelBannerComponent', () => {
  let fixture: ComponentFixture<AiAssistedLabelBannerComponent>;
  let component: AiAssistedLabelBannerComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiAssistedLabelBannerComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AiAssistedLabelBannerComponent);
    component = fixture.componentInstance;
  });

  // ── Scenario 1: warning banner ─────────────────────────────────────────────

  it('should show warning banner for ai_assisted_label=true AND status=PENDING_REVIEW', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'PENDING_REVIEW';
    component.ngOnChanges({});
    fixture.detectChanges();

    const banner = fixture.debugElement.query(By.css('.ai-assisted-banner'));
    expect(banner).toBeTruthy();
    expect(banner.nativeElement.textContent).toContain('AI-Assisted');
    expect(banner.nativeElement.textContent).toContain('Review Required');
  });

  it('should show warning banner for ai_assisted_label=true AND status=DRAFT', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'DRAFT';
    component.ngOnChanges({});
    fixture.detectChanges();

    const banner = fixture.debugElement.query(By.css('.ai-assisted-banner'));
    expect(banner).toBeTruthy();
  });

  it('should NOT show warning banner when ai_assisted_label=false', () => {
    component.aiAssistedLabel = false;
    component.documentStatus = 'PENDING_REVIEW';
    component.ngOnChanges({});
    fixture.detectChanges();

    const banner = fixture.debugElement.query(By.css('.ai-assisted-banner'));
    expect(banner).toBeNull();
  });

  // ── Scenario 2: approved footer, no banner ─────────────────────────────────

  it('should NOT show warning banner when status=APPROVED', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'APPROVED';
    component.ngOnChanges({});
    fixture.detectChanges();

    const banner = fixture.debugElement.query(By.css('.ai-assisted-banner'));
    expect(banner).toBeNull();
  });

  it('should show approved footer when status=APPROVED', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'APPROVED';
    component.reviewedByDisplayName = 'Dr. David Chen';
    component.approvedAt = new Date('2026-07-16T10:00:00Z');
    component.ngOnChanges({});
    fixture.detectChanges();

    const footer = fixture.debugElement.query(By.css('.approved-footer'));
    expect(footer).toBeTruthy();
    expect(footer.nativeElement.textContent).toContain('Dr. David Chen');
  });

  it('should NOT show approved footer when status=PENDING_REVIEW', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'PENDING_REVIEW';
    component.ngOnChanges({});
    fixture.detectChanges();

    const footer = fixture.debugElement.query(By.css('.approved-footer'));
    expect(footer).toBeNull();
  });

  // ── Accessibility ──────────────────────────────────────────────────────────

  it('should have role="alert" on warning banner for screen reader accessibility', () => {
    component.aiAssistedLabel = true;
    component.documentStatus = 'PENDING_REVIEW';
    component.ngOnChanges({});
    fixture.detectChanges();

    const banner = fixture.debugElement.query(By.css('[role="alert"]'));
    expect(banner).toBeTruthy();
  });
});
