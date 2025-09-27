import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

// Helper copied/adapted from main spec to drain initial log requests
/**
 * Drain initial log requests to keep specs stable and avoid cross-run flakiness.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function flushInitialLogs(httpMock: HttpTestingController) {
  const logs = httpMock.match(
    (request) =>
      request.method === 'GET' &&
      (request.url.startsWith('/logs/refresh/') ||
        request.url.startsWith('/logs/level/') ||
        request.url.startsWith('/logs/tail')),
  );
  for (const r of logs) {
    const url = r.request.url;
    if (url.startsWith('/logs/refresh/')) {
      r.flush({ name: 'api', interval_ms: 0, lines: 200 });
    } else if (url.startsWith('/logs/level/')) {
      r.flush({ service: 'api', level: undefined });
    } else if (url.startsWith('/logs/tail')) {
      r.flush({
        name: 'api',
        path: './logs/api.log',
        content: 'initial log content',
        missing: false,
      });
    }
  }
}

describe('AppComponent extra coverage', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    flushInitialLogs(httpMock);
    httpMock.verify();
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('formatAuthError normalizes common statuses and messages', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    // Initial addresses load
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance as unknown as {
      formatAuthError: (
        error: unknown,
        fallback: string,
        overrides?: Record<number, string>,
      ) => string;
    };

    expect(comp.formatAuthError({ status: 0 }, 'x')).toMatch(
      /cannot reach server/i,
    );
    expect(comp.formatAuthError({ status: 401 }, 'x')).toMatch(/unauthorized/i);
    expect(comp.formatAuthError({ status: 404 }, 'x')).toMatch(/not found/i);
    expect(comp.formatAuthError({ status: 503 }, 'x')).toMatch(/unavailable/i);
    // Backend-provided error takes precedence
    expect(
      comp.formatAuthError(
        { status: 500, error: { error: 'boom' } },
        'fallback',
      ),
    ).toBe('boom');
    // Overrides by status
    expect(
      comp.formatAuthError({ status: 401 }, 'x', { 401: 'bad creds' }),
    ).toBe('bad creds');
  });

  it('saveRefresh persists settings and starts interval that fetches tail', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    // Initial addresses
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance;
    comp.logTab = 'api';
    comp.refreshMs = 25;
    comp.logLines = 200;

    comp.saveRefresh();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/refresh/api',
    );
    expect(put.request.body).toEqual({ interval_ms: 25, lines: 200 });
    put.flush({ status: 'ok' });

    // The interval should trigger a tail fetch after ~refreshMs
    tick(30);
    const tail = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    expect(tail.request.params.get('name')).toBe('api');
    tail.flush({
      name: 'api',
      path: './logs/api.log',
      content: 'tick',
      missing: false,
    });

    // Stop timer to avoid leakage
    fixture.destroy();
  }));

  it('saveLevel persists API level', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance;
    comp.logTab = 'api';
    comp.currentLevel = 'DEBUG';
    comp.saveLevel();

    const request = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/level/api',
    );
    expect(request.request.body).toEqual({ level: 'DEBUG' });
    request.flush({ status: 'ok' });
  });

  it('setBackendStatusFromError sets status banners correctly', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance as unknown as {
      setBackendStatusFromError: (error: unknown) => void;
      backendNotReady: boolean;
      backendUnreachable: boolean;
    };
    comp.setBackendStatusFromError({ status: 503 });
    expect(comp.backendNotReady).toBeTrue();
    expect(comp.backendUnreachable).toBeFalse();

    comp.setBackendStatusFromError({ status: 0 });
    expect(comp.backendUnreachable).toBeTrue();
  });

  it('applyLocalFilter filters by id, pattern, and regex label', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);

    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'alpha@example.com', is_regex: false },
        { id: 2, pattern: 'beta@example.com', is_regex: true },
      ] as Entry[]);

    const comp = fixture.componentInstance;
    expect(comp.entries.length).toBe(2);

    // Filter by pattern substring
    comp.localFilter = 'beta';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(1);
    expect(comp.filteredEntries[0].pattern).toContain('beta');

    // Filter by id
    comp.localFilter = '1';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(1);
    expect(comp.filteredEntries[0].id).toBe(1);

    // Filter by regex label "yes"
    comp.localFilter = 'yes';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(1);
    expect(comp.filteredEntries[0].is_regex).toBeTrue();
  });
});
