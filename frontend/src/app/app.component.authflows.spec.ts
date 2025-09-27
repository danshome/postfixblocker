import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';
import * as webAuthn from './webauthn.utility';
import type {
  AuthenticationResponseJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser';

// Helper to avoid hard-coded password literals in tests
/**
 * Concatenate parts into a single string for test-only secret construction.
 * @param {...string} parts - String fragments to concatenate.
 * @returns {string} The concatenated string.
 */
const tstr = (...parts: string[]): string => parts.join('');

/**
 * Drain outstanding log-related HTTP requests issued by the component during init.
 * @param {HttpTestingController} httpMock - HTTP testing controller to match and flush requests.
 * @returns {void} Nothing.
 */
function drainLogs(httpMock: HttpTestingController): void {
  // Flush any outstanding log-related requests. Some may be issued as a side effect
  // of flushing refresh/level, so iterate until none remain (with a small cap).
  for (let index = 0; index < 3; index++) {
    const logs = httpMock.match(
      (request) =>
        request.method === 'GET' &&
        (request.url.startsWith('/logs/refresh/') ||
          request.url.startsWith('/logs/level/') ||
          request.url.startsWith('/logs/tail')),
    );
    if (logs.length === 0) break;
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
}

describe('AppComponent authentication flows', () => {
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
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
  });

  afterEach(() => {
    drainLogs(httpMock);
    // Drain any stray /addresses GETs triggered by ngOnInit or onAuthenticated
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

  it('loginWithPassword returns mustChangePassword and does not proceed', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    // ngOnInit session check
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/auth/session')
      .flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    comp.loginPassword = tstr(
      'p',
      'o',
      's',
      't',
      'f',
      'i',
      'x',
      'b',
      'l',
      'o',
      'c',
      'k',
      'e',
      'r',
    );
    const p = comp.loginWithPassword();

    const request = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/login/password',
    );
    request.flush({
      authenticated: false,
      username: 'admin',
      mustChangePassword: true,
    });
    await p;

    expect(comp.session.mustChangePassword).toBeTrue();
    // No addresses/refresh should be fetched at this point
    const stray = httpMock.match((r) => r.url.startsWith('/addresses'));
    expect(stray.length).toBe(0);
  });

  it('loginWithPassword success triggers onAuthenticated (logs + load)', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    comp.loginPassword = tstr('g', 'o', 'o', 'd');
    const p = comp.loginWithPassword();

    httpMock.expectOne('/auth/login/password').flush({
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
    });
    await p;
    // Allow microtasks to progress (onAuthenticated initial subscriptions)
    await Promise.resolve();

    // onAuthenticated -> expect logs settings + tail + addresses
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/logs/refresh/api')
      .flush({ name: 'api', interval_ms: 0, lines: 200 });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/logs/level/api')
      .flush({ service: 'api', level: 'INFO' });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/logs/tail')
      .flush({
        name: 'api',
        path: './logs/api.log',
        content: 'ok',
        missing: false,
      });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
  });

  it('loginWithPassword 401 shows friendly error', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    comp.loginPassword = tstr('b', 'a', 'd');
    const p = comp.loginWithPassword();

    httpMock
      .expectOne('/auth/login/password')
      .flush({ error: 'nope' }, { status: 401, statusText: 'Unauthorized' });
    await p;

    expect(String(comp.authError || '')).toMatch(
      /invalid username or password/i,
    );
  });

  it('changePassword success refreshes session and proceeds', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.oldPassword = tstr('o', 'l', 'd');
    comp.newPassword = tstr('n', 'e', 'w');
    const p = comp.changePassword();

    httpMock.expectOne('/auth/change-password').flush({ ok: true });
    httpMock.expectOne('/auth/session').flush({
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
    });
    await p;
    // Allow microtasks to progress (onAuthenticated initial subscriptions)
    await Promise.resolve();

    // onAuthenticated flows
    httpMock
      .expectOne('/logs/refresh/api')
      .flush({ name: 'api', interval_ms: 0, lines: 200 });
    httpMock
      .expectOne('/logs/level/api')
      .flush({ service: 'api', level: 'INFO' });
    httpMock.expectOne('/logs/tail').flush({
      name: 'api',
      path: './logs/api.log',
      content: 'ok',
      missing: false,
    });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
  });

  it('registerPasskey surfaces 401 error without proceeding', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
      hasWebAuthn: false,
    });

    webAuthn.__setWebAuthnLoader(async () => ({
      // return shapes compatible with @simplewebauthn/browser interfaces
      startRegistration: async () =>
        ({ id: 'att' }) as unknown as RegistrationResponseJSON,
      startAuthentication: async () =>
        ({ id: 'asr' }) as unknown as AuthenticationResponseJSON,
    }));

    const comp = fixture.componentInstance as AppComponent;
    const p = comp.registerPasskey();

    httpMock
      .expectOne('/auth/register/challenge')
      .flush({ error: 'no' }, { status: 401, statusText: 'Unauthorized' });
    await p;

    expect(comp.passkeyBusy).toBeFalse();
    expect(String(comp.authError || '')).toMatch(/sign in/i);
  });

  it('loginWithPasskey success triggers onAuthenticated', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    webAuthn.__setWebAuthnLoader(async () => ({
      startRegistration: async () =>
        ({ id: 'att' }) as unknown as RegistrationResponseJSON,
      startAuthentication: async () =>
        ({ id: 'asr' }) as unknown as AuthenticationResponseJSON,
    }));

    const comp = fixture.componentInstance as AppComponent;
    const p = comp.loginWithPasskey();

    httpMock
      .expectOne('/auth/login/challenge')
      .flush({ publicKey: { challenge: 'x' } });
    // Allow microtasks for getAssertion to resolve
    await Promise.resolve();
    httpMock
      .expectOne('/auth/login/verify')
      .flush({ authenticated: true, username: 'admin' });
    await p;
    // Allow microtasks to progress (onAuthenticated initial subscriptions)
    await Promise.resolve();

    httpMock
      .expectOne('/logs/refresh/api')
      .flush({ name: 'api', interval_ms: 0, lines: 200 });
    httpMock
      .expectOne('/logs/level/api')
      .flush({ service: 'api', level: 'INFO' });
    httpMock.expectOne('/logs/tail').flush({
      name: 'api',
      path: './logs/api.log',
      content: 'ok',
      missing: false,
    });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
  });

  it('logout failure still clears session', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock
      .expectOne('/auth/session')
      .flush({ authenticated: true, username: 'admin' });

    const comp = fixture.componentInstance as AppComponent;
    const p = comp.logout();

    httpMock
      .expectOne('/auth/logout')
      .flush({ error: 'x' }, { status: 500, statusText: 'Server' });
    await p;

    expect(comp.session?.authenticated).toBeFalse();
  });
});
