#!/usr/bin/env node
/**
 * Validation script for Document Review Routing
 * 
 * Verifies routing configuration for /documents/:id/review
 */

const fs = require('fs');
const path = require('path');

console.log('\n' + '='.repeat(80));
console.log('DOCUMENT REVIEW ROUTING VALIDATION');
console.log('='.repeat(80) + '\n');

const routesFile = path.join(__dirname, '..', 'src', 'app', 'app.routes.ts');
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

try {
  const routesContent = fs.readFileSync(routesFile, 'utf8');
  
  console.log('Route Configuration Checks:');
  console.log('-'.repeat(80));
  
  check(
    routesContent.includes("path: 'documents/:id/review'"),
    'Document review route path configured'
  );
  
  check(
    routesContent.includes('canActivate: [authGuard]') && 
    routesContent.match(/documents\/:id\/review[\s\S]*?canActivate/),
    'Auth guard applied to document review route'
  );
  
  check(
    routesContent.includes('document-review/document-review.component'),
    'DocumentReviewComponent import path configured'
  );
  
  check(
    routesContent.includes('DocumentReviewComponent'),
    'DocumentReviewComponent referenced in route'
  );
  
  check(
    routesContent.includes('loadComponent'),
    'Lazy loading configured for route'
  );
  
  console.log();
  console.log('Component Existence Checks:');
  console.log('-'.repeat(80));
  
  const componentPath = path.join(
    __dirname, 
    '..', 
    'src', 
    'app', 
    'features', 
    'documents',
    'document-review',
    'document-review.component.ts'
  );
  
  check(
    fs.existsSync(componentPath),
    'DocumentReviewComponent file exists'
  );
  
  if (fs.existsSync(componentPath)) {
    const componentContent = fs.readFileSync(componentPath, 'utf8');
    
    check(
      componentContent.includes('DocumentService'),
      'DocumentReviewComponent imports DocumentService'
    );
    
    check(
      componentContent.includes('ChangeLogTimelineComponent'),
      'DocumentReviewComponent imports ChangeLogTimelineComponent'
    );
    
    check(
      componentContent.includes('ActivatedRoute'),
      'DocumentReviewComponent uses ActivatedRoute for route params'
    );
  }
  
  console.log();
  console.log('Service Existence Checks:');
  console.log('-'.repeat(80));
  
  const servicePath = path.join(
    __dirname,
    '..',
    'src',
    'app',
    'features',
    'documents',
    'services',
    'document.service.ts'
  );
  
  check(
    fs.existsSync(servicePath),
    'DocumentService file exists'
  );
  
  if (fs.existsSync(servicePath)) {
    const serviceContent = fs.readFileSync(servicePath, 'utf8');
    
    check(
      serviceContent.includes('getDocument(documentId: string)'),
      'DocumentService.getDocument() method exists'
    );
    
    check(
      serviceContent.includes('saveDraft('),
      'DocumentService.saveDraft() method exists'
    );
    
    check(
      serviceContent.includes('getChangeLog('),
      'DocumentService.getChangeLog() method exists'
    );
    
    check(
      serviceContent.includes("providedIn: 'root'"),
      'DocumentService is provided in root'
    );
  }
  
  console.log();
  console.log('='.repeat(80));
  console.log(`VALIDATION SUMMARY: ${passed} passed, ${failed} failed`);
  console.log('='.repeat(80));
  console.log();
  
  if (failed > 0) {
    console.log('⚠ Some validation checks failed. Please review the configuration.');
    process.exit(1);
  } else {
    console.log('✓ All validation checks passed!');
    console.log();
    console.log('Routing Configuration Complete:');
    console.log('  • Route: /documents/:id/review');
    console.log('  • Component: DocumentReviewComponent (lazy loaded)');
    console.log('  • Guard: authGuard (authentication required)');
    console.log('  • Service: DocumentService (available)');
    console.log('  • Timeline: ChangeLogTimelineComponent (integrated)');
    console.log();
    console.log('Usage Examples:');
    console.log('  • Navigate to: /documents/123e4567-e89b-12d3-a456-426614174000/review');
    console.log('  • Route parameter: id (document ID)');
    console.log('  • Access in component: this.route.snapshot.paramMap.get("id")');
    console.log();
    console.log('Next Steps:');
    console.log('  1. Test navigation to document review page');
    console.log('  2. Verify auth guard redirects unauthenticated users');
    console.log('  3. Confirm DocumentService API calls work');
    console.log('  4. Test ChangeLogTimelineComponent rendering');
    console.log();
    process.exit(0);
  }
} catch (error) {
  console.error('✗ Error during validation:', error.message);
  process.exit(1);
}
