import type { Entry } from './app-logic.service';
import { AppLogicService } from './app-logic.service';

describe('AppLogicService', () => {
  it('selection helpers: computeDragMode, toggleInSet, clickPostDrag', () => {
    const svc2 = new AppLogicService();
    expect(svc2.computeDragMode(false)).toBe('select');
    expect(svc2.computeDragMode(true)).toBe('deselect');
    const set = new Set<number>();
    svc2.toggleInSet(set, 1, true);
    expect(set.has(1)).toBeTrue();
    svc2.toggleInSet(set, 1, false);
    expect(set.has(1)).toBeFalse();
    const post1 = svc2.clickPostDrag(true);
    expect(post1.ignore).toBeTrue();
    expect(post1.nextSuppressClick).toBeFalse();
    const post2 = svc2.clickPostDrag(false);
    expect(post2.ignore).toBeFalse();
  });
  let svc: AppLogicService;

  beforeEach(() => {
    svc = new AppLogicService();
  });

  it('parseBulkText trims, filters empties, preserves order, and de-duplicates', () => {
    const raw =
      '  a@example.com  \n\nA@example.com\n  b@example.com  \n a@example.com ';
    const out = svc.parseBulkText(raw);
    expect(out).toEqual(['a@example.com', 'A@example.com', 'b@example.com']);
  });

  it('parseBulkText returns empty array for blank input', () => {
    expect(svc.parseBulkText('  \n\t ')).toEqual([]);
  });

  it('filterEntries returns a copy when query is blank and filters by id/pattern/is_regex', () => {
    const entries: Entry[] = [
      { id: 1, pattern: 'Alice@Example.com', is_regex: false },
      { id: 2, pattern: '.*@corp.com', is_regex: true },
    ];
    // Blank -> copy
    const noq = svc.filterEntries(entries, '');
    expect(noq).not.toBe(entries);
    expect(noq).toEqual(entries);
    // By id
    expect(svc.filterEntries(entries, '2').map((entry) => entry.id)).toEqual([
      2,
    ]);
    // By pattern (case-insensitive)
    expect(
      svc.filterEntries(entries, 'alice').map((entry) => entry.id),
    ).toEqual([1]);
    // By is_regex (yes/no)
    expect(svc.filterEntries(entries, 'yes').map((entry) => entry.id)).toEqual([
      2,
    ]);
  });

  it('formatAuthError respects overrides and status-specific messages', () => {
    // Overrides win
    expect(svc.formatAuthError({ status: 401 }, 'fb', { 401: 'bad' })).toBe(
      'bad',
    );
    // Backend-provided message
    expect(svc.formatAuthError({ error: { error: 'boom' } }, 'fb')).toBe(
      'boom',
    );
    // Status mappings
    expect(svc.formatAuthError({ status: 0 }, 'fb')).toMatch(/cannot reach/i);
    expect(svc.formatAuthError({ status: 401 }, 'fb')).toMatch(/unauthorized/i);
    expect(svc.formatAuthError({ status: 404 }, 'fb')).toMatch(/not found/i);
    expect(svc.formatAuthError({ status: 503 }, 'fb')).toMatch(/unavailable/i);
    // Fallback to message or statusText then fallback
    expect(svc.formatAuthError({ message: 'm' }, 'fb')).toBe('m');
    expect(svc.formatAuthError({}, 'fb')).toBe('fb');
  });

  it('backendStatusFromError returns correct banner flags', () => {
    expect(svc.backendStatusFromError({ status: 503 })).toEqual({
      backendNotReady: true,
      backendUnreachable: false,
    });
    expect(svc.backendStatusFromError({ status: 0 })).toEqual({
      backendNotReady: false,
      backendUnreachable: true,
    });
    expect(svc.backendStatusFromError({ status: 500 })).toEqual({
      backendNotReady: false,
      backendUnreachable: false,
    });
  });

  it('shouldFallbackOnEditStatus covers 404/405/501 true and 409/undefined false', () => {
    expect(svc.shouldFallbackOnEditStatus(404)).toBeTrue();
    expect(svc.shouldFallbackOnEditStatus(405)).toBeTrue();
    expect(svc.shouldFallbackOnEditStatus(501)).toBeTrue();
    expect(svc.shouldFallbackOnEditStatus(409)).toBeFalse();
    expect(svc.shouldFallbackOnEditStatus()).toBeFalse();
  });

  it('afterSessionDecision returns proceed and mustChange flags correctly', () => {
    expect(
      svc.afterSessionDecision({
        authenticated: true,
        mustChangePassword: false,
      }),
    ).toEqual({ proceed: true, mustChange: false });
    expect(
      svc.afterSessionDecision({
        authenticated: true,
        mustChangePassword: true,
      }),
    ).toEqual({ proceed: false, mustChange: true });
    expect(
      svc.afterSessionDecision({
        authenticated: false,
        mustChangePassword: false,
      }),
    ).toEqual({ proceed: false, mustChange: false });
    expect(svc.afterSessionDecision()).toEqual({
      proceed: false,
      mustChange: false,
    });
  });
});
