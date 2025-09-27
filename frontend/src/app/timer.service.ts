import { Injectable } from '@angular/core';

/**
 * TimerService abstracts scheduling primitives so tests can provide a fake
 * implementation that tracks intervals and controls time deterministically.
 * Provides thin wrappers over global setInterval/clearInterval for easier mocking.
 */
@Injectable({ providedIn: 'root' })
export class TimerService {
  /**
   * Schedule a recurring callback.
   * @param {() => void} handler - Function to invoke on each interval tick.
   * @param {number} timeout - Interval duration in milliseconds.
   * @returns {number} Interval identifier that can be passed to clearInterval.
   */
  setInterval(handler: () => void, timeout: number): number {
    return globalThis.setInterval(handler, timeout) as unknown as number;
  }
  /**
   * Cancel a previously scheduled interval.
   * @param {number} id - Identifier returned from setInterval.
   * @returns {void} Nothing.
   */
  clearInterval(id: number): void {
    try {
      globalThis.clearInterval(id);
    } catch {
      /* no-op */
    }
  }
}
