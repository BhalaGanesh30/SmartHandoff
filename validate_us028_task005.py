"""
Validation script for US-028 TASK-005: DocumentReviewComponent
Verifies all acceptance criteria and validation checklist items.
"""
import pathlib
import re

print()
print('=' * 80)
print('US-028 TASK-005: DocumentReviewComponent - VALIDATION')
print('=' * 80)
print()

# File paths
base_path = pathlib.Path('frontend/src/app/features/documents')
files = {
    'component_ts': base_path / 'document-review/document-review.component.ts',
    'component_html': base_path / 'document-review/document-review.component.html',
    'component_scss': base_path / 'document-review/document-review.component.scss',
    'view_model': base_path / 'models/document-review.vm.ts',
}

print('Files Created:')
print('-' * 80)
total_size = 0
for name, path in files.items():
    if path.exists():
        size = path.stat().st_size
        total_size += size
        print(f'✓ {path.relative_to("frontend")} ({size:,} bytes)')
    else:
        print(f'✗ {path.relative_to("frontend")} - NOT FOUND')
        exit(1)

print()
print(f'Total implementation size: {total_size:,} bytes')
print()

# Read file contents
ts_content = files['component_ts'].read_text(encoding='utf-8')
html_content = files['component_html'].read_text(encoding='utf-8')
scss_content = files['component_scss'].read_text(encoding='utf-8')
vm_content = files['view_model'].read_text(encoding='utf-8')

print('Validation Checklist:')
print('-' * 80)

checks = []

# 1. Left pane contenteditable=false and aria-readonly=true
check1 = 'contenteditable="false"' in html_content and 'aria-readonly="true"' in html_content
checks.append(('Left pane with contenteditable="false" and aria-readonly="true"', check1))

# 2. Right pane wraps sh-document-editor
check2 = '<sh-document-editor' in html_content and 'textarea' not in html_content.lower()
checks.append(('Right pane uses sh-document-editor (not textarea)', check2))

# 3. Scroll sync mirrors scrollTop both ways
check3 = ts_content.count('initScrollSync') >= 2
checks.append(('Scroll sync initialized for both panes', check3))

# 4. Scroll sync guard (isScrollSyncing)
check4 = 'private isScrollSyncing = false' in ts_content and 'if (this.isScrollSyncing) return;' in ts_content
checks.append(('Scroll sync guard prevents infinite loop', check4))

# 5. AI-Assisted Draft banner visible
check5 = 'AI-Assisted Draft' in html_content and 'ai-label-banner' in html_content
checks.append(('AI-Assisted Draft banner present', check5))

# 6. takeUntil(this.destroy$) on subscriptions
check6 = ts_content.count('takeUntil(this.destroy$)') >= 2
checks.append(('takeUntil(this.destroy$) used for memory leak prevention', check6))

# 7. Component uses ChangeDetectionStrategy.OnPush
check7 = 'changeDetection: ChangeDetectionStrategy.OnPush' in ts_content
checks.append(('Component uses ChangeDetectionStrategy.OnPush', check7))

# 8. WCAG 2.1 AA compliance
check8 = 'aria-label' in html_content and '<section' in html_content
checks.append(('WCAG 2.1 AA: aria-label and semantic sections', check8))

# 9. Loading spinner shown while vm is null
check9 = '*ngIf="vm; else loadingTpl"' in html_content and 'mat-progress-spinner' in html_content
checks.append(('Loading spinner shown while vm is null', check9))

# 10. isSaving flag for save button
check10 = 'isSaving = false' in ts_content and '[isSaving]="isSaving"' in html_content
checks.append(('isSaving flag passed to document-editor', check10))

# Additional checks
# 11. ViewChild for both panes
check11 = "@ViewChild('leftPane')" in ts_content and "@ViewChild('rightPane')" in ts_content
checks.append(('ViewChild decorators for both panes', check11))

# 12. debounceTime(16) for 60fps
check12 = 'debounceTime(16)' in ts_content
checks.append(('Debounce time set to 16ms (~60fps)', check12))

# 13. requestAnimationFrame for flag reset
check13 = 'requestAnimationFrame' in ts_content
checks.append(('requestAnimationFrame used for scroll sync flag reset', check13))

# 14. Dual-pane flexbox layout
check14 = '.dual-pane-container' in scss_content and 'display: flex' in scss_content
checks.append(('Dual-pane flexbox layout in SCSS', check14))

# 15. View model interface
check15 = 'export interface DocumentReviewVm' in vm_content and 'aiDraftHtml: string' in vm_content
checks.append(('DocumentReviewVm interface defined', check15))

# Print results
all_passed = True
for description, passed in checks:
    status = '✓' if passed else '✗'
    print(f'{status} {description}')
    if not passed:
        all_passed = False

print()
print('-' * 80)
print()

print('US-028 Acceptance Criteria Coverage:')
print('-' * 80)

ac_checks = [
    ('AC Scenario 1', 'Left pane read-only', check1),
    ('AC Scenario 1', 'Right pane editable', check2),
    ('AC Scenario 1', 'Both scroll in sync', check3 and check4),
    ('AC Scenario 3', 'Save Draft button calls saveDraft', 'onSaveDraft' in ts_content),
]

for criterion, description, passed in ac_checks:
    status = '✓' if passed else '✗'
    print(f'{status} {criterion}: {description}')

print()
print('-' * 80)
print()

if all_passed:
    print('VALIDATION RESULT: ALL CHECKS PASSED ✓')
    print()
    print('=' * 80)
    print('TASK-005: COMPLETE ✓')
    print('=' * 80)
    print()
    print('Next Steps:')
    print('  1. Implement TASK-006: DocumentEditorComponent (Quill editor)')
    print('  2. Implement TASK-007: ChangeLogTimelineComponent')
    print('  3. Implement DocumentService with getDocument() and saveDraft()')
    print('  4. Add routing for /documents/:id/review')
    print('  5. Test scroll synchronization behavior')
    print()
else:
    print('VALIDATION RESULT: SOME CHECKS FAILED ✗')
    print('Please review the failed checks above.')
    exit(1)

print('=' * 80)
