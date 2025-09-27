import { Injectable } from '@angular/core';

export interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 * Narrow representation of HTTP-ish error objects used by the UI.
 */
interface BackendErrorPayload {
  error?: string;
  message?: string;
}
export interface HttpErrorLike {
  status?: number;
  error?: BackendErrorPayload | Record<string, unknown> | string;
  message?: string;
  statusText?: string;
}

/** Session payload shape sufficient for UI decisions. */
interface SessionLike {
  authenticated?: boolean;
  mustChangePassword?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AppLogicService {
  /**
   * Compute drag mode for multi-select gestures.
   * @param {boolean} currentlySelected - Whether the row is already selected.
   * @returns {"select"|"deselect"} "deselect" when selected, otherwise "select".
   */
  computeDragMode(currentlySelected: boolean): 'select' | 'deselect' {
    return currentlySelected ? 'deselect' : 'select';
  }

  /**
   * Toggle an id inside a Set based on a checkbox state.
   * @param {Set<number>} set - Target selection set to mutate.
   * @param {number} id - Identifier to add or remove.
   * @param {boolean} checked - When true add, otherwise remove.
   */
  toggleInSet(set: Set<number>, id: number, checked: boolean): void {
    if (checked) set.add(id);
    else set.delete(id);
  }

  /**
   * Compute click handling after a drag gesture.
   * @param {boolean} suppressClick - If true, ignore this click but clear the suppression.
   * @returns {{ignore: boolean, nextSuppressClick: boolean}} Flags indicating whether to ignore the click and next suppression state.
   */
  clickPostDrag(suppressClick: boolean): {
    ignore: boolean;
    nextSuppressClick: boolean;
  } {
    if (suppressClick) {
      return { ignore: true, nextSuppressClick: false };
    }
    return { ignore: false, nextSuppressClick: false };
  }

  /**
   * Parse bulk textarea into a unique, ordered list of patterns.
   * First-seen casing and order are preserved; duplicates are removed case-sensitively.
   * @param {string} raw - Raw textarea content possibly containing newlines.
   * @returns {string[]} Array of unique patterns in first-seen order.
   */
  parseBulkText(raw: string): string[] {
    const lines = (raw || '')
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (lines.length === 0) return [];
    const seen = new Set<string>();
    const out: string[] = [];
    for (const s of lines) {
      if (!seen.has(s)) {
        seen.add(s);
        out.push(s);
      }
    }
    return out;
  }

  /**
   * Client-side filter for entries shown in the current page.
   * Matches by id, case-insensitive pattern, or regex flag ("yes"/"no").
   * @param {Entry[]} entries - Entries to filter.
   * @param {string} query - Free-text query.
   * @returns {Entry[]} Filtered entries.
   */
  filterEntries(entries: Entry[], query: string): Entry[] {
    const q = (query || '').trim().toLowerCase();
    if (!q) return [...entries];
    return entries.filter((entry) => {
      const id = String(entry.id);
      const pattern = (entry.pattern || '').toLowerCase();
      const isRegex = entry.is_regex ? 'yes' : 'no';
      return id.includes(q) || pattern.includes(q) || isRegex.includes(q);
    });
  }

  /**
   * Normalize backend/auth errors into friendly messages.
   * @param {HttpErrorLike|undefined} error - HTTP-like error object possibly containing status and nested payload.
   * @param {string} fallback - Message to use if no details are available.
   * @param {Record<number, string>=} overrides - Optional status-to-message overrides.
   * @returns {string} A human-friendly string to display.
   */
  /**
   * Pick an override message for a status code from a Record or Map.
   * @param {number|undefined} status - HTTP status to look up.
   * @param {Readonly<Record<number,string>>|ReadonlyMap<number,string>|undefined} overrides - Optional overrides source.
   * @returns {string|undefined} The mapped message if present.
   */
  private pickOverride(
    status: number | undefined,
    overrides?: Readonly<Record<number, string>> | ReadonlyMap<number, string>,
  ): string | undefined {
    if (!overrides || typeof status !== 'number') return undefined;
    if (overrides instanceof Map) return overrides.get(status);
    const m = new Map<number, string>(
      Object.entries(overrides).map(([k, v]) => [Number(k), String(v)]),
    );
    return m.get(status);
  }

  /**
   * Extract a backend-provided error message from an HTTP-like error object.
   * @param {HttpErrorLike|undefined} error - The error object.
   * @returns {string} Message if present; otherwise an empty string.
   */
  private extractBackendMessage(error: HttpErrorLike | undefined): string {
    const raw = error?.error;
    if (raw && typeof raw === 'object') {
      const maybe = raw as BackendErrorPayload;
      return String(maybe.error || maybe.message || '');
    }
    if (typeof raw === 'string') return raw;
    return '';
  }

  formatAuthError(
    error: HttpErrorLike | undefined,
    fallback: string,
    overrides?: Readonly<Record<number, string>> | ReadonlyMap<number, string>,
  ): string {
    const status: number | undefined =
      typeof error?.status === 'number' ? error.status : undefined;

    const mapped = this.pickOverride(status, overrides);
    if (mapped) return mapped;

    const backendMessage = this.extractBackendMessage(error);
    if (backendMessage) return backendMessage;

    switch (status) {
      case 0: {
        return 'Cannot reach server. Please check your connection and try again.';
      }
      case 401: {
        return 'Unauthorized. Please check your credentials or sign in again.';
      }
      case 404: {
        return 'Not found.';
      }
      case 503: {
        return 'Service unavailable. Please try again shortly.';
      }
      default: {
        const message = error?.message || error?.statusText;
        return message ? String(message) : fallback;
      }
    }
  }

  /**
   * Compute backend status banner flags from an error object.
   * @param {HttpErrorLike|undefined} error - HTTP-like error object.
   * @returns {{backendNotReady: boolean, backendUnreachable: boolean}} Flags indicating backend readiness and reachability.
   */
  backendStatusFromError(error: HttpErrorLike | undefined): {
    backendNotReady: boolean;
    backendUnreachable: boolean;
  } {
    const status = error?.status ?? 0;
    return {
      backendNotReady: status === 503,
      backendUnreachable: status === 0,
    };
  }

  /**
   * Decide if inline-edit should fall back to POST+DELETE for an error status.
   * @param {number|undefined} status - HTTP status code from a failed inline edit.
   * @returns {boolean} True when a fallback flow should be attempted.
   */
  shouldFallbackOnEditStatus(status?: number): boolean {
    return status === 404 || status === 405 || status === 501;
  }

  /**
   * Decide whether to proceed with app loading after fetching a session.
   * @param {SessionLike|null|undefined} sess - Session object or undefined.
   * @returns {{proceed: boolean, mustChange: boolean}} Proceed flag and whether the user must change password.
   */
  afterSessionDecision(sess?: SessionLike | null): {
    proceed: boolean;
    mustChange: boolean;
  } {
    const authenticated = !!sess?.authenticated;
    const mustChange = !!sess?.mustChangePassword;
    return { proceed: authenticated && !mustChange, mustChange };
  }
}
