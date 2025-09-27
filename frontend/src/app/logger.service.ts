import { Injectable } from '@angular/core';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'none';

/**
 *
 */
@Injectable({ providedIn: 'root' })
export class LoggerService {
  level: LogLevel = 'info';

  /**
   * Set the minimum log level for subsequent messages.
   * @param level - New log level threshold.
   */
  setLevel(level: LogLevel): void {
    this.level = level;
  }

  /**
   * Decide if a message at the given level should be emitted for the current threshold.
   * @param target - Target log level for the message.
   */
  private shouldLog(target: LogLevel): boolean {
    const order: LogLevel[] = ['debug', 'info', 'warn', 'error', 'none'];
    const currentIndex = order.indexOf(this.level);
    const tgtIndex = order.indexOf(target);
    return tgtIndex >= currentIndex && this.level !== 'none';
  }

  /**
   * Emit a debug-level message.
   * @param {...unknown} arguments_ - Values to log.
   */
  debug(...arguments_: unknown[]): void {
    if (this.shouldLog('debug'))
      try {
        console.warn('[debug]', ...arguments_);
      } catch {
        /* no-op */
      }
  }
  /**
   * Emit an info-level message.
   * @param {...unknown} arguments_ - Values to log.
   */
  info(...arguments_: unknown[]): void {
    if (this.shouldLog('info'))
      try {
        console.warn('[info]', ...arguments_);
      } catch {
        /* no-op */
      }
  }
  /**
   * Emit a warning-level message.
   * @param {...unknown} arguments_ - Values to log.
   */
  warn(...arguments_: unknown[]): void {
    if (this.shouldLog('warn'))
      try {
        console.warn(...arguments_);
      } catch {
        /* no-op */
      }
  }
  /**
   * Emit an error-level message.
   * @param {...unknown} arguments_ - Values to log.
   */
  error(...arguments_: unknown[]): void {
    if (this.shouldLog('error'))
      try {
        console.error(...arguments_);
      } catch {
        /* no-op */
      }
  }
}
