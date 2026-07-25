/**
 * Unit tests for EncounterTasksApiService.
 *
 * Tests cover:
 *   - getTasksForEncounter returns task array
 *   - getTaskById returns single task
 *   - getTasksByStatus filters by status
 *   - getTasksByRole filters by role
 *   - Error handling for HTTP failures
 *   - Retry logic on transient failures
 */
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { EncounterTasksApiService } from './encounter-tasks-api.service';
import { AgentTaskResponse } from '../models/task.model';
import { environment } from '../../../environments/environment';

describe('EncounterTasksApiService', () => {
  let service: EncounterTasksApiService;
  let httpMock: HttpTestingController;

  const mockTask: AgentTaskResponse = {
    id: 'task-123',
    encounter_id: 'enc-001',
    unit_id: '3A',
    agent_type: 'DOCUMENTATION',
    target_role: 'nurse',
    status: 'IN_PROGRESS',
    start_time: '2026-07-25T10:00:00Z',
    completed_time: null,
    payload: { note: 'Test task' },
    output: null,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [EncounterTasksApiService],
    });
    service = TestBed.inject(EncounterTasksApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should fetch tasks for an encounter', () => {
    service.getTasksForEncounter('enc-001').subscribe(tasks => {
      expect(tasks).toEqual([mockTask]);
    });

    const req = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks`);
    expect(req.request.method).toBe('GET');
    req.flush([mockTask]);
  });

  it('should fetch a task by ID', () => {
    service.getTaskById('task-123').subscribe(task => {
      expect(task).toEqual(mockTask);
    });

    const req = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/tasks/task-123`);
    expect(req.request.method).toBe('GET');
    req.flush(mockTask);
  });

  it('should fetch tasks filtered by status', () => {
    service.getTasksByStatus('enc-001', 'COMPLETED').subscribe(tasks => {
      expect(tasks).toEqual([mockTask]);
    });

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks?status=COMPLETED`
    );
    expect(req.request.method).toBe('GET');
    req.flush([mockTask]);
  });

  it('should fetch tasks filtered by role', () => {
    service.getTasksByRole('enc-001', 'nurse').subscribe(tasks => {
      expect(tasks).toEqual([mockTask]);
    });

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks?role=nurse`
    );
    expect(req.request.method).toBe('GET');
    req.flush([mockTask]);
  });

  it('should handle HTTP errors gracefully', () => {
    service.getTasksForEncounter('enc-001').subscribe({
      next: () => fail('should have failed with 404 error'),
      error: (error) => {
        expect(error.message).toContain('Server error 404');
      },
    });

    const req = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks`);
    req.flush({ detail: 'Encounter not found' }, { status: 404, statusText: 'Not Found' });
  });

  it('should retry on transient failures', () => {
    let attempt = 0;
    service.getTasksForEncounter('enc-001').subscribe({
      next: tasks => {
        expect(tasks).toEqual([mockTask]);
        expect(attempt).toBe(2); // Initial + 2 retries
      },
    });

    // First attempt fails
    const req1 = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks`);
    attempt++;
    req1.flush(null, { status: 500, statusText: 'Internal Server Error' });

    // Second attempt fails
    const req2 = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks`);
    attempt++;
    req2.flush(null, { status: 500, statusText: 'Internal Server Error' });

    // Third attempt succeeds
    const req3 = httpMock.expectOne(`${environment.apiBaseUrl}/api/v1/encounters/enc-001/tasks`);
    attempt++;
    req3.flush([mockTask]);
  });
});
