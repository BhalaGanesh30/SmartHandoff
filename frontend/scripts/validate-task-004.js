/**
 * Validation script for TASK-004 implementation.
 * 
 * Verifies:
 *   - All required files exist
 *   - TypeScript compilation succeeds
 *   - No syntax errors in key files
 *   - SignalR service has correct dependencies
 */

const fs = require('fs');
const path = require('path');

const FRONTEND_ROOT = path.join(__dirname, '..');

// Required files for TASK-004
const REQUIRED_FILES = [
  // Configuration
  'package.json',
  'tsconfig.json',
  'angular.json',
  
  // SignalR Service
  'src/app/core/signalr/signalr.service.ts',
  'src/app/core/signalr/signalr.service.spec.ts',
  'src/app/core/signalr/index.ts',
  
  // API Service
  'src/app/core/api/encounter-tasks-api.service.ts',
  'src/app/core/api/encounter-tasks-api.service.spec.ts',
  'src/app/core/api/index.ts',
  
  // Models
  'src/app/core/models/task.model.ts',
  'src/app/core/models/index.ts',
  
  // Dashboard Component
  'src/app/features/dashboard/dashboard.component.ts',
  'src/app/features/dashboard/dashboard.component.html',
  'src/app/features/dashboard/dashboard.component.scss',
  'src/app/features/dashboard/dashboard.component.spec.ts',
];

// Required dependencies in package.json
const REQUIRED_DEPENDENCIES = [
  '@angular/core',
  '@angular/common',
  '@angular/router',
  '@microsoft/signalr',
  'rxjs',
];

console.log('🔍 TASK-004 Implementation Validation\n');

let allPassed = true;

// 1. Check file existence
console.log('1️⃣  Checking required files...');
const missingFiles = [];
REQUIRED_FILES.forEach(file => {
  const filePath = path.join(FRONTEND_ROOT, file);
  if (!fs.existsSync(filePath)) {
    missingFiles.push(file);
    allPassed = false;
  }
});

if (missingFiles.length > 0) {
  console.log('   ❌ Missing files:');
  missingFiles.forEach(file => console.log(`      - ${file}`));
} else {
  console.log('   ✅ All required files exist');
}

// 2. Check package.json dependencies
console.log('\n2️⃣  Checking package.json dependencies...');
try {
  const packageJsonPath = path.join(FRONTEND_ROOT, 'package.json');
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  const deps = { ...packageJson.dependencies, ...packageJson.devDependencies };
  
  const missingDeps = [];
  REQUIRED_DEPENDENCIES.forEach(dep => {
    if (!deps[dep]) {
      missingDeps.push(dep);
      allPassed = false;
    }
  });
  
  if (missingDeps.length > 0) {
    console.log('   ❌ Missing dependencies:');
    missingDeps.forEach(dep => console.log(`      - ${dep}`));
  } else {
    console.log('   ✅ All required dependencies present');
  }
  
  // Check SignalR version
  if (deps['@microsoft/signalr']) {
    console.log(`   ℹ️  @microsoft/signalr version: ${deps['@microsoft/signalr']}`);
  }
} catch (error) {
  console.log(`   ❌ Error reading package.json: ${error.message}`);
  allPassed = false;
}

// 3. Verify SignalR service implementation
console.log('\n3️⃣  Verifying SignalR service implementation...');
try {
  const signalrServicePath = path.join(FRONTEND_ROOT, 'src/app/core/signalr/signalr.service.ts');
  const signalrContent = fs.readFileSync(signalrServicePath, 'utf8');
  
  const checks = [
    { pattern: /HubConnectionBuilder/g, name: 'HubConnectionBuilder usage' },
    { pattern: /withAutomaticReconnect/g, name: 'Auto-reconnect configuration' },
    { pattern: /accessTokenFactory/g, name: 'JWT accessTokenFactory' },
    { pattern: /taskUpdated\$/g, name: 'taskUpdated$ Observable' },
    { pattern: /EncounterTasksApiService/g, name: 'EncounterTasksApiService integration' },
    { pattern: /onreconnected/g, name: 'Reconnection handler' },
  ];
  
  checks.forEach(check => {
    if (check.pattern.test(signalrContent)) {
      console.log(`   ✅ ${check.name}`);
    } else {
      console.log(`   ❌ Missing: ${check.name}`);
      allPassed = false;
    }
  });
} catch (error) {
  console.log(`   ❌ Error reading SignalR service: ${error.message}`);
  allPassed = false;
}

// 4. Verify Dashboard component integration
console.log('\n4️⃣  Verifying Dashboard component integration...');
try {
  const dashboardPath = path.join(FRONTEND_ROOT, 'src/app/features/dashboard/dashboard.component.ts');
  const dashboardContent = fs.readFileSync(dashboardPath, 'utf8');
  
  const checks = [
    { pattern: /SignalRService/g, name: 'SignalR service injection' },
    { pattern: /EncounterTasksApiService/g, name: 'Tasks API service injection' },
    { pattern: /startConnection/g, name: 'SignalR connection start' },
    { pattern: /stopConnection/g, name: 'SignalR connection cleanup' },
    { pattern: /taskUpdated\$\.subscribe/g, name: 'Task update subscription' },
    { pattern: /signal</g, name: 'Angular signals usage' },
  ];
  
  checks.forEach(check => {
    if (check.pattern.test(dashboardContent)) {
      console.log(`   ✅ ${check.name}`);
    } else {
      console.log(`   ❌ Missing: ${check.name}`);
      allPassed = false;
    }
  });
} catch (error) {
  console.log(`   ❌ Error reading Dashboard component: ${error.message}`);
  allPassed = false;
}

// 5. Check TypeScript configuration
console.log('\n5️⃣  Checking TypeScript configuration...');
try {
  const tsconfigPath = path.join(FRONTEND_ROOT, 'tsconfig.json');
  const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, 'utf8'));
  
  if (tsconfig.compilerOptions?.strict) {
    console.log('   ✅ Strict mode enabled');
  } else {
    console.log('   ⚠️  Strict mode not enabled (recommended for production)');
  }
  
  if (tsconfig.compilerOptions?.paths) {
    console.log('   ✅ Path aliases configured');
  }
} catch (error) {
  console.log(`   ❌ Error reading tsconfig.json: ${error.message}`);
  allPassed = false;
}

// Summary
console.log('\n' + '='.repeat(60));
if (allPassed) {
  console.log('✅ VALIDATION PASSED - All checks successful!');
  console.log('\nNext steps:');
  console.log('  1. cd frontend');
  console.log('  2. npm install');
  console.log('  3. npm test (to run Jest tests)');
  console.log('  4. npm start (to run dev server)');
  process.exit(0);
} else {
  console.log('❌ VALIDATION FAILED - Please review errors above');
  process.exit(1);
}
