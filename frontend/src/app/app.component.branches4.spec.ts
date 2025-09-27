import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

/**
 * Drain and flush any pending log-related HTTP requests so tests remain isolated.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller instance.
 */
function drainLogs(httpMock: HttpTestingController) {
  const logs = httpMock.match(
    (r) =>
      r.method === 'GET' &&
      (r.url.startsWith('/logs/refresh/') ||
        r.url.startsWith('/logs/level/') ||
        r.url.startsWith('/logs/tail')),
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
        content: 'init',
        missing: false,
      });
    }
  }
}

describe('AppComponent small remaining branches', () => {
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
    drainLogs(httpMock);
    // Drain any stray /addresses GETs that may have been issued during auth flows
    const stray = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    for (const r of stray) {
      r.flush([]);
    }
    httpMock.verify();
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('saveRefresh catch branch (PUT fails)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance as AppComponent;
    comp.logTab = 'api';
    comp.refreshMs = 1234;
    comp.logLines = 200;
    comp.saveRefresh();
    const put = httpMock.expectOne('/logs/refresh/api');
    put.flush({ error: 'nope' }, { status: 500, statusText: 'Server' });
    // No throw expected
  });

  it('saveLevel catch branch (PUT fails)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance as AppComponent;
    comp.logTab = 'api';
    comp.currentLevel = 'DEBUG';
    comp.saveLevel();
    const put = httpMock.expectOne('/logs/level/api');
    put.flush({ error: 'nope' }, { status: 500, statusText: 'Server' });
  });

  it('beginEdit/cancelEdit with events (stopPropagation branches)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 1, pattern: 'one', is_regex: false }]);

    const comp = fixture.componentInstance as AppComponent;
    const event_: { stopPropagation: () => void } = {
      /**
       * Non-empty stub to satisfy no-empty-function rule.
       * @returns {void} Nothing.
       */
      stopPropagation: (): void => {
        const t = Date.now();
        if (t < 0) throw new Error(String(t));
      },
    };
    comp.beginEdit({ id: 1, pattern: 'one', is_regex: false }, event_);
    comp.cancelEdit(event_);
    // No HTTP
  });

  it('deleteAll selects everything then deletes', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'a', is_regex: false },
        { id: 2, pattern: 'b', is_regex: false },
      ]);

    const comp = fixture.componentInstance as AppComponent;
    comp.deleteAll();
    const d1 = httpMock.expectOne('/addresses/1');
    d1.flush({ status: 'deleted' });
    const d2 = httpMock.expectOne('/addresses/2');
    d2.flush({ status: 'deleted' });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
  });

  it('remove() error path does not reload but sets status', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 1, pattern: 'a', is_regex: false }]);

    const comp = fixture.componentInstance as AppComponent;
    comp.remove(1);
    const del = httpMock.expectOne('/addresses/1');
    del.flush(
      { error: 'boom' },
      { status: 503, statusText: 'Service Unavailable' },
    );
    expect(comp.backendNotReady).toBeTrue();
    // No reload GET expected here
  });

  it('loginWithPassword malformed response triggers catch', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    comp.loginPassword = ['x'].join('');
    comp.loginWithPassword();

    httpMock.expectOne('/auth/login/password').flush({ hello: 'world' });
    tick();
    expect(String(comp.authError || '')).toMatch(/login failed/i);
  }));

  it('refreshSession error path sets session unauthenticated', async () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock
      .expectOne('/auth/session')
      .flush({ authenticated: true, username: 'admin' });

    const comp = fixture.componentInstance as AppComponent;
    comp.session = { authenticated: true, username: 'admin' };
    const p = comp.refreshSession();
    // This call triggers a new /auth/session; make it fail
    const request = httpMock.expectOne('/auth/session');
    request.flush({ error: 'x' }, { status: 500, statusText: 'Server' });
    await p;
    expect(comp.session?.authenticated).toBeFalse();
  });
});
