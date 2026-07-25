/**
 * Unit tests for DashboardComponent.
 *
 * Tests cover:
 *   - Component initialization with encounter ID
 *   - Initial task loading
 *   - SignalR connection establishment
 *   - Real-time task update handling
 *   - Manual refresh functionality
 *   - Error handling
 *   - Computed signals (pending, in-progress, completed tasks)
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { DashboardComponent } from './dashboard.component';
import { SignalRService, TaskUpdatedEvent } from '../../core/signalr';
import { EncounterTasksApiService } from '../../core/api';
import { AgentTaskResponse, TaskStatus } from '../../core/models';

describe('DashboardComponent', () => {
  let component: DashboardComponent;
  let fixture: ComponentFixture<DashboardComponent>;
  let mockSignalRService: any;
  let mockTasksApiService: any;
  let mockActivatedRoute: any;
  let taskUpdatedSubject: Subject<TaskUpdatedEvent>;

  const mockTask: AgentTaskResponse = {
    id: 'task-123',
    encounter_id: 'enc-001',
    unit_id: '3A',
    agent_type: 'DOCUMENTATION',
    target_role: 'nurse',
    status: TaskStatus.IN_PROGRESS,
    start_time: '2026-07-25T10:00:00Z',
    completed_time: null,
    payload: null,
    output: null,
  };

  beforeEach(async () => {
    taskUpdatedSubject = new Subject<TaskUpdatedEvent>();

    mockSignalRService = {
      startConnection: jest.fn().mockResolvedValue(undefined),
      stopConnection: jest.fn().mockResolvedValue(undefined),
      taskUpdated$: taskUpdatedSubject.asObservable(),
    };

    mockTasksApiService = {
      getTasksForEncounter: jest.fn().mockReturnValue(of([mockTask])),
      getTaskById: jest.fn().mockReturnValue(of(mockTask)),
    };

    mockActivatedRoute = {
      params: of({ encounterId: 'enc-001' }),
    };

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        { provide: SignalRService, useValue: mockSignalRService },
        { provide: EncounterTasksApiService, useValue: mockTasksApiService },
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load initial tasks on init', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mockTasksApiService.getTasksForEncounter).toHaveBeenCalledWith('enc-001');
    expect(component.tasks()).toEqual([mockTask]);
    expect(component.isLoading()).toBe(false);
  });

  it('should start SignalR connection on init', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mockSignalRService.startConnection).toHaveBeenCalledWith('enc-001');
  });

  it('should update task when task_updated event is received', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    const updateEvent: TaskUpdatedEvent = {
      task_id: 'task-123',
      encounter_id: 'enc-001',
      unit_id: '3A',
      role_name: 'nurse',
      agent_type: 'DOCUMENTATION',
      previous_status: TaskStatus.IN_PROGRESS,
      new_status: TaskStatus.COMPLETED,
      updated_at: '2026-07-25T11:00:00Z',
    };

    taskUpdatedSubject.next(updateEvent);
    fixture.detectChanges();

    const updatedTask = component.tasks()[0];
    expect(updatedTask.status).toBe(TaskStatus.COMPLETED);
    expect(updatedTask.completed_time).toBe('2026-07-25T11:00:00Z');
  });

  it('should compute pending tasks correctly', async () => {
    component.tasks.set([
      { ...mockTask, status: TaskStatus.PENDING },
      { ...mockTask, id: 'task-2', status: TaskStatus.IN_PROGRESS },
    ]);

    expect(component.pendingTasks().length).toBe(1);
    expect(component.pendingTasks()[0].status).toBe(TaskStatus.PENDING);
  });

  it('should refresh tasks manually', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    mockTasksApiService.getTasksForEncounter.mockReturnValue(
      of([mockTask, { ...mockTask, id: 'task-2' }])
    );

    component.refreshTasks();
    await fixture.whenStable();

    expect(mockTasksApiService.getTasksForEncounter).toHaveBeenCalledTimes(2);
    expect(component.tasks().length).toBe(2);
  });

  it('should handle API errors gracefully', async () => {
    mockTasksApiService.getTasksForEncounter.mockReturnValue(
      throwError(() => new Error('API Error'))
    );

    fixture.detectChanges();
    await fixture.whenStable();

    expect(component.errorMessage()).toContain('Failed to initialize dashboard');
    expect(component.isLoading()).toBe(false);
  });

  it('should stop SignalR connection on destroy', () => {
    fixture.detectChanges();
    component.ngOnDestroy();

    expect(mockSignalRService.stopConnection).toHaveBeenCalled();
  });
});
