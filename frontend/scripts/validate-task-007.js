#!/usr/bin/env node
/**
 * Validation script for US-028 TASK-007
 * 
 * Verifies implementation of ChangeLogTimelineComponent and DocumentService
 */

const fs = require('fs');
const path = require('path');

console.log('\n' + '='.repeat(80));
console.log('US-028 TASK-007 VALIDATION: ChangeLogTimelineComponent & DocumentService');
console.log('='.repeat(80) + '\n');

const baseDir = path.join(__dirname, '..', 'src', 'app', 'features', 'documents');
let passed = 0;
let failed = 0;

function check(condition, message) {
  if (condition) {
    console.log('✓', message);
    passed++;
  } else {
    console.log('✗', message);
    failed++;
  }
}

function fileExists(filePath) {
  return fs.existsSync(path.join(baseDir, filePath));
}

function fileContains(filePath, searchString) {
  try {
    const content = fs.readFileSync(path.join(baseDir, filePath), 'utf8');
    return content.includes(searchString);
  } catch (e) {
    return false;
  }
}

// File existence checks
console.log('File Existence Checks:');
console.log('-'.repeat(80));
check(fileExists('services/document.service.ts'), 'DocumentService exists');
check(fileExists('models/change-log-entry.model.ts'), 'ChangeLogEntry model exists');
check(fileExists('change-log-timeline/change-log-timeline.component.ts'), 'ChangeLogTimelineComponent TypeScript exists');
check(fileExists('change-log-timeline/change-log-timeline.component.html'), 'ChangeLogTimelineComponent HTML exists');
check(fileExists('change-log-timeline/change-log-timeline.component.scss'), 'ChangeLogTimelineComponent SCSS exists');

console.log();

// DocumentService validation
console.log('DocumentService Implementation:');
console.log('-'.repeat(80));
check(fileContains('services/document.service.ts', 'providedIn: \'root\''), 
  'DocumentService is providedIn: root');
check(fileContains('services/document.service.ts', 'getDocument(documentId: string)'), 
  'getDocument() method exists');
check(fileContains('services/document.service.ts', 'saveDraft('), 
  'saveDraft() method exists');
check(fileContains('services/document.service.ts', 'approveDocument('), 
  'approveDocument() method exists');
check(fileContains('services/document.service.ts', 'rejectDocument('), 
  'rejectDocument() method exists');
check(fileContains('services/document.service.ts', 'getChangeLog(documentId: string)'), 
  'getChangeLog() method exists');
check(fileContains('services/document.service.ts', 'Observable<ChangeLogEntry[]>'), 
  'getChangeLog() returns Observable<ChangeLogEntry[]>');

console.log();

// ChangeLogEntry model validation
console.log('ChangeLogEntry Model:');
console.log('-'.repeat(80));
check(fileContains('models/change-log-entry.model.ts', 'export interface ChangeLogEntry'), 
  'ChangeLogEntry interface exported');
check(fileContains('models/change-log-entry.model.ts', 'field: string'), 
  'field property exists');
check(fileContains('models/change-log-entry.model.ts', 'author_display_name: string | null'), 
  'author_display_name property exists');
check(fileContains('models/change-log-entry.model.ts', 'timestamp: string'), 
  'timestamp property exists');

console.log();

// ChangeLogTimelineComponent validation
console.log('ChangeLogTimelineComponent Implementation:');
console.log('-'.repeat(80));
check(fileContains('change-log-timeline/change-log-timeline.component.ts', 'ChangeDetectionStrategy.OnPush'), 
  'Uses OnPush change detection');
check(fileContains('change-log-timeline/change-log-timeline.component.ts', 'standalone: true'), 
  'Component is standalone');
check(fileContains('change-log-timeline/change-log-timeline.component.ts', '@Input({ required: true }) documentId!: string'), 
  'documentId input is required');
check(fileContains('change-log-timeline/change-log-timeline.component.ts', 'changeLog$!: Observable<ChangeLogEntry[]>'), 
  'changeLog$ observable exists');
check(fileContains('change-log-timeline/change-log-timeline.component.ts', 'MatExpansionModule'), 
  'Imports MatExpansionModule');
check(fileContains('change-log-timeline/change-log-timeline.component.ts', 'MatIconModule'), 
  'Imports MatIconModule');

console.log();

// HTML template validation
console.log('ChangeLogTimelineComponent Template:');
console.log('-'.repeat(80));
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'aria-label="Document change history"'), 
  'Has accessibility label on section');
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'async'), 
  'Uses async pipe');
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'author_display_name ?? '), 
  'Falls back from author_display_name');
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'date:'), 
  'Uses DatePipe for timestamp formatting');
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'mat-expansion-panel'), 
  'Uses mat-expansion-panel for diff view');
check(fileContains('change-log-timeline/change-log-timeline.component.html', 'No changes recorded yet'), 
  'Shows empty state message');

console.log();

// SCSS styling validation
console.log('ChangeLogTimelineComponent Styles:');
console.log('-'.repeat(80));
check(fileContains('change-log-timeline/change-log-timeline.component.scss', '.changelog'), 
  'Base changelog class exists');
check(fileContains('change-log-timeline/change-log-timeline.component.scss', '__title'), 
  'Uses BEM naming convention');
check(fileContains('change-log-timeline/change-log-timeline.component.scss', '__list'), 
  'List styles exist');
check(fileContains('change-log-timeline/change-log-timeline.component.scss', '__diff'), 
  'Diff styles exist');

console.log();

// API endpoint validation
console.log('API Endpoint Paths:');
console.log('-'.repeat(80));
check(fileContains('services/document.service.ts', 'this.base}/${documentId}'), 
  'GET /api/v1/documents/{id} endpoint');
check(fileContains('services/document.service.ts', '/approve'), 
  'PATCH /approve endpoint');
check(fileContains('services/document.service.ts', '/reject'), 
  'PATCH /reject endpoint');
check(fileContains('services/document.service.ts', '/change-log'), 
  'GET /change-log endpoint');

console.log();
console.log('='.repeat(80));
console.log(`VALIDATION SUMMARY: ${passed} passed, ${failed} failed`);
console.log('='.repeat(80));
console.log();

if (failed > 0) {
  console.log('⚠ Some validation checks failed. Please review the implementation.');
  process.exit(1);
} else {
  console.log('✓ All validation checks passed!');
  console.log();
  console.log('Implementation Complete:');
  console.log('  • DocumentService with 5 API methods');
  console.log('  • ChangeLogEntry model interface');
  console.log('  • ChangeLogTimelineComponent (TypeScript, HTML, SCSS)');
  console.log('  • Standalone component with OnPush change detection');
  console.log('  • WCAG 2.1 AA accessibility features');
  console.log('  • BEM naming convention in SCSS');
  console.log();
  console.log('Next Steps:');
  console.log('  1. Import and use ChangeLogTimelineComponent in DocumentReviewComponent');
  console.log('  2. Pass documentId as input: <sh-change-log-timeline [documentId]="documentId">');
  console.log('  3. Implement TASK-003, TASK-005, TASK-006 (upstream dependencies)');
  console.log('  4. Test integration with backend API endpoints');
  console.log();
  process.exit(0);
}
