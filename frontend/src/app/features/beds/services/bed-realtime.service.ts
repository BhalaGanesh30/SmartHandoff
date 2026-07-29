import { Injectable, inject } from '@angular/core';
import { SignalRService } from '@core/signalr/signalr.service';
import { BedUpdateEvent } from '../models/bed.model';

/**
 * UpdateCallback type — callback signature for bed status updates.
 * Strongly typed callback to ensure safe invocation of bed state mutations.
 */
type UpdateCallback = (event: BedUpdateEvent) => void;

/**
 * BedRealtimeService — Subscribes to SignalR bed_status_changed events
 * and delegates cell state updates to BedBoardComponent via callback.
 * Satisfies US-050 Scenario 2: bed cell updates within 1 second of ADT event.
 *
 * Usage:
 *   constructor(private bedRealtime: BedRealtimeService) {}
 *   ngOnInit() {
 *     this.bedRealtime.start((event) => this.updateBedStatus(event.bedId, patch));
 *   }
 *   ngOnDestroy() {
 *     this.bedRealtime.stop();
 *   }
 */
@Injectable({ providedIn: 'root' })
export class BedRealtimeService {
  private readonly signalR = inject(SignalRService);
  private updateCallback: UpdateCallback | null = null;

  /**
   * Registers the update callback and attaches the SignalR listener.
   * Call once from BedBoardComponent.ngOnInit() after initial data load.
   * @param onUpdate Callback invoked each time a bed_status_changed event is received.
   */
  start(onUpdate: UpdateCallback): void {
    this.updateCallback = onUpdate;
    this.signalR.on<BedUpdateEvent>('bed_status_changed', event => {
      this.updateCallback?.(event);
    });
  }

  /**
   * Removes the SignalR listener and nulls the callback.
   * Call from BedBoardComponent.ngOnDestroy() to prevent memory leaks.
   */
  stop(): void {
    this.signalR.off('bed_status_changed');
    this.updateCallback = null;
  }
}