/**
 * SignalRService — manages the Azure SignalR WebSocket connection for real-time
 * task_updated events on the care team dashboard.
 *
 * US-022 requirements:
 *   - HubConnectionBuilder with accessTokenFactory (Scenario 4 — JWT auth)
 *   - withAutomaticReconnect with custom retry schedule (Scenario 3 — <5s reconnect)
 *   - task_updated event exposes taskUpdated$ Observable (Scenario 1 — <1s latency)
 *   - On reconnect, re-fetches missed tasks (Scenario 3 — no missed updates)
 *
 * Design: Angular standalone service (providedIn: 'root'); uses inject() API.
 * RxJS Subject bridges SignalR callback to Angular Observable.
 */
import { Injectable, OnDestroy, inject } from '@angular/core';
import {
  HubConnection,
  HubConnectionBuilder,
  HubConnectionState,
  LogLevel,
} from '@microsoft/signalr';
import { Subject, Observable } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { EncounterTasksApiService } from '../api/encounter-tasks-api.service';
import { environment } from '../../../environments/environment';

/** Payload received from the SignalR `task_updated` event.
 *  Mirrors TaskUpdatedPayload on the FastAPI backend (US-022 TASK-001). */
export interface TaskUpdatedEvent {
  task_id: string;
  encounter_id: string;
  unit_id: string;
  role_name: string;
  agent_type: string;
  previous_status: string;
  new_status: string;
  updated_at: string;
}

/** Retry intervals for withAutomaticReconnect — targets <5s reconnect (US-022 Scenario 3). */
const RECONNECT_DELAYS_MS = [0, 1000, 2000, 5000, 10000];

@Injectable({ providedIn: 'root' })
export class SignalRService implements OnDestroy {
  private readonly authService = inject(AuthService);
  private readonly encounterTasksApi = inject(EncounterTasksApiService);

  private connection: HubConnection | null = null;
  private readonly _taskUpdated$ = new Subject<TaskUpdatedEvent>();
  private currentEncounterId: string | null = null;

  /** Observable of task_updated events. Subscribe in DashboardComponent. */
  readonly taskUpdated$: Observable<TaskUpdatedEvent> = this._taskUpdated$.asObservable();

  /** Initiates the SignalR connection for the given encounter context.
   *
   * Calls the negotiate endpoint (TASK-002) — the accessTokenFactory ensures the
   * JWT is attached to every connection and reconnection attempt.
   *
   * @param encounterId - Active encounter ID; used to re-fetch missed tasks on reconnect.
   */
  async startConnection(encounterId: string): Promise<void> {
    if (this.connection?.state === HubConnectionState.Connected) {
      return;
    }

    this.currentEncounterId = encounterId;

    this.connection = new HubConnectionBuilder()
      .withUrl(`${environment.apiBaseUrl}/api/v1/signalr/negotiate`, {
        // US-022 Technical Notes: accessTokenFactory injects JWT for every connection.
        // The negotiate endpoint (TASK-002) validates this JWT before issuing the
        // Azure SignalR client token.
        accessTokenFactory: () => this.authService.getToken() ?? '',
      })
      .withAutomaticReconnect(RECONNECT_DELAYS_MS)
      .configureLogging(environment.production ? LogLevel.Warning : LogLevel.Information)
      .build();

    this._registerEventHandlers();
    this._registerReconnectHandlers();

    await this.connection.start();
  }

  /** Gracefully stops the connection. Call on component destroy or logout. */
  async stopConnection(): Promise<void> {
    if (this.connection) {
      await this.connection.stop();
      this.connection = null;
    }
  }

  ngOnDestroy(): void {
    this.stopConnection().catch(() => {
      // Swallow stop errors on destroy — connection may already be closed.
    });
    this._taskUpdated$.complete();
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private _registerEventHandlers(): void {
    if (!this.connection) return;

    // US-022 Scenario 1: listen for task_updated events from the hub.
    this.connection.on('task_updated', (payload: TaskUpdatedEvent) => {
      this._taskUpdated$.next(payload);
    });
  }

  private _registerReconnectHandlers(): void {
    if (!this.connection) return;

    this.connection.onreconnecting(() => {
      // Dashboard can show a "Reconnecting…" indicator via taskUpdated$ subscribers.
    });

    this.connection.onreconnected(async () => {
      if (this.currentEncounterId) {
        try {
          const tasks = await this.encounterTasksApi
            .getTasksForEncounter(this.currentEncounterId)
            .toPromise();
          if (tasks) {
            // Emit a synthetic task_updated for each task so the dashboard
            // re-renders to the current server state without requiring a full reload.
            tasks.forEach(task => {
              this._taskUpdated$.next({
                task_id: task.id,
                encounter_id: this.currentEncounterId!,
                unit_id: task.unit_id ?? '',
                role_name: task.target_role ?? '',
                agent_type: task.agent_type,
                previous_status: task.status,
                new_status: task.status,
                updated_at: task.completed_time ?? task.start_time,
              });
            });
          }
        } catch (error) {
          // Reconnect re-fetch is best-effort — log only.
          console.error('Failed to re-fetch tasks on reconnect:', error);
        }orEncounter(this.currentEncounterId).toPromise();
        // and emit synthetic task_updated events for each task
      }
    });

    this.connection.onclose(() => {
      // Connection permanently closed (all retry attempts exhausted).
      // Dashboard should surface an actionable "Connection lost — please refresh" banner.
      console.error('SignalR connection closed permanently');
    });
  }
}
