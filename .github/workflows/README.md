# GitHub Actions Workflows

This directory contains CI/CD pipeline configurations for SmartHandoff.

## Workflows

### 1. `pr-checks.yml`
- Runs on: Pull request creation/update
- Purpose: Fast feedback for unit tests and linting
- Excludes: Performance tests (marked with `@pytest.mark.performance`)

### 2. `staging-performance-gate.yml`
- Runs on: Manual trigger or post-merge to `main`
- Purpose: Validates p95 latency SLA against staging environment
- Includes: TASK-007 performance test suite

### 3. `deploy-staging.yml`
- Runs on: Successful staging gate
- Purpose: Deploys to staging Cloud Run services

### 4. `deploy-production.yml`
- Runs on: Manual approval after staging validation
- Purpose: Deploys to production Cloud Run services

---

For detailed configuration, see individual workflow files.
