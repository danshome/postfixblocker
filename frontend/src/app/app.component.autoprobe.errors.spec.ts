import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

/**
 * Drain and flush all pending HTTP requests to avoid cross-spec leakage.
 * @param {HttpTestingController} httpMock - HTTP testing controller to match and flush requests.
 * @returns {void} Nothing.
 */
function drainAll(httpMock: HttpTestingController): void {
  const reqs = httpMock.match(() => true);
  for (const r of reqs) {
    if (r.request.method === 'GET' && r.request.url === '/auth/session') {
      r.flush({ authenticated: false });
    } else if (
      r.request.method === 'GET' &&
      (r.request.url.startsWith('/logs/refresh/') ||
        r.request.url.startsWith('/logs/level/') ||
        r.request.url.startsWith('/logs/tail'))
    ) {
      r.flush({});
    } else if (
      r.request.method === 'GET' &&
      r.request.url.startsWith('/addresses')
    ) {
      r.flush([]);
    } else if (
      r.request.method === 'POST' &&
      r.request.url === '/auth/login/password'
    ) {
      r.flush({ error: 'x' }, { status: 401, statusText: 'Unauthorized' });
    } else {
      r.flush({});
    }
  }
}

describe('AppComponent auto-probe error branches', () => {
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
    drainAll(httpMock);
    httpMock.verify();
    (
      globalThis as { __USE_AUTH__?: boolean; __PROBE_AUTH__?: boolean }
    ).__USE_AUTH__ = undefined;
    (
      globalThis as { __USE_AUTH__?: boolean; __PROBE_AUTH__?: boolean }
    ).__PROBE_AUTH__ = undefined;
    expect().nothing();
  });

  it('when __PROBE_AUTH__ is true, a 401 on probe enables auth and avoids data loads', fakeAsync(() => {
    (globalThis as { __PROBE_AUTH__?: boolean }).__PROBE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    tick();

    // First probe -> 401 triggers enable auth branch
    const p1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    p1.flush({ error: 'unauth' }, { status: 401, statusText: 'Unauthorized' });
    tick();

    // Strict session check after flipping useAuth
    const s2 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s2.flush({ authenticated: false });
    tick();

    // No logs or addresses should load while unauthenticated
    const stray = httpMock.match(
      (r) => r.url.startsWith('/logs/') || r.url.startsWith('/addresses'),
    );
    expect(stray.length).toBe(0);
  }));

  it('loginWithPassword response without authenticated flag surfaces friendly error and does not proceed', async () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // Initial strict session
    const s1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s1.flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    // eslint-disable-next-line sonarjs/no-hardcoded-passwords -- test-only placeholder improves clarity without risk
    comp.loginPassword = 'x';
    const p = comp.loginWithPassword();

    const lp = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/login/password',
    );
    // Missing authenticated field triggers friendly error path
    lp.flush({ username: 'admin' });
    await p;

    expect(String(comp.authError || '')).toMatch(/login failed/i);

    // Ensure no data/log loads occurred
    const stray = httpMock.match(
      (r) => r.url.startsWith('/logs/') || r.url.startsWith('/addresses'),
    );
    expect(stray.length).toBe(0);
  });
});
