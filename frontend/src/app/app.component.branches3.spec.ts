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

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 * Drain log requests; side effects can enqueue new ones, so loop until none remain.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainInitial(httpMock: HttpTestingController) {
  // Drain log requests; side effects can enqueue new ones, so loop until none remain.
  for (let index = 0; index < 3; index++) {
    const logs = httpMock.match(
      (r) =>
        r.method === 'GET' &&
        (r.url.startsWith('/logs/refresh/') ||
          r.url.startsWith('/logs/level/') ||
          r.url.startsWith('/logs/tail')),
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

describe('AppComponent remaining branches', () => {
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
    drainInitial(httpMock);
    httpMock.verify();
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('load() error 503 sets backendNotReady and clears entries', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    // First addresses GET errors with 503
    const get1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    get1.flush(
      { error: 'db not ready' },
      { status: 503, statusText: 'Service Unavailable' },
    );

    const comp = fixture.componentInstance as AppComponent;
    expect(comp.backendNotReady).toBeTrue();
    expect(comp.entries.length).toBe(0);
  });

  it('toggleSelectAll true then false affects selection', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'a', is_regex: false },
        { id: 2, pattern: 'b', is_regex: false },
      ] as Entry[]);

    const comp = fixture.componentInstance;
    comp.toggleSelectAll(true);
    expect(comp.isSelected(1)).toBeTrue();
    expect(comp.isSelected(2)).toBeTrue();
    comp.toggleSelectAll(false);
    expect(comp.isSelected(1)).toBeFalse();
    expect(comp.isSelected(2)).toBeFalse();
  });

  it('changePassword 401 surfaces error', () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.oldPassword = ['o', 'l', 'd'].join('');
    comp.newPassword = ['n', 'e', 'w'].join('');
    comp.changePassword();

    httpMock
      .expectOne('/auth/change-password')
      .flush({ error: 'nope' }, { status: 401, statusText: 'Unauthorized' });
    expect(String(comp.authError || '')).toMatch(/old password is incorrect/i);
  });

  it('registerPasskey success flow updates session', async () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
      hasWebAuthn: false,
    });

    webAuthn.__setWebAuthnLoader(
      async () =>
        ({
          /**
           * Return a minimal RegistrationResponseJSON-like object.
           * @returns {Promise<RegistrationResponseJSON>} Stubbed response.
           */
          startRegistration: async (): Promise<RegistrationResponseJSON> =>
            ({ id: 'att' }) as unknown as RegistrationResponseJSON,
          /**
           * Return a minimal AuthenticationResponseJSON-like object.
           * @returns {Promise<AuthenticationResponseJSON>} Stubbed response.
           */
          startAuthentication: async (): Promise<AuthenticationResponseJSON> =>
            ({ id: 'asr' }) as unknown as AuthenticationResponseJSON,
        }) as unknown as {
          startRegistration: () => Promise<RegistrationResponseJSON>;
          startAuthentication: () => Promise<AuthenticationResponseJSON>;
        },
    );

    const comp = fixture.componentInstance as AppComponent;
    comp.registerPasskey();

    httpMock
      .expectOne('/auth/register/challenge')
      .flush({ publicKey: { challenge: 'x' } });
    httpMock
      .expectOne('/auth/register/verify')
      .flush({ authenticated: true, username: 'admin', hasWebAuthn: true });
    expect(comp.session?.hasWebAuthn).toBeTrue();
  });

  it('loginWithPasskey 404 shows helpful message', async () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/auth/session').flush({ authenticated: false });

    const comp = fixture.componentInstance as AppComponent;
    comp.loginWithPasskey();

    httpMock
      .expectOne('/auth/login/challenge')
      .flush({ error: 'none' }, { status: 404, statusText: 'Not Found' });
    expect(String(comp.authError || '')).toMatch(/no passkey registered/i);
  });

  it('setSelectedToEnforceMode issues PUT per id and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 5, pattern: 'a', is_regex: false, test_mode: true },
        { id: 6, pattern: 'b', is_regex: false, test_mode: true },
      ] as Entry[]);

    const comp = fixture.componentInstance;
    comp.toggleSelect(5, true);
    comp.toggleSelect(6, true);
    comp.setSelectedToEnforceMode();

    const u1 = httpMock.expectOne('/addresses/5');
    expect(u1.request.method).toBe('PUT');
    expect(u1.request.body).toEqual({ test_mode: false });
    u1.flush({ status: 'ok' });
    const u2 = httpMock.expectOne('/addresses/6');
    expect(u2.request.body).toEqual({ test_mode: false });
    u2.flush({ status: 'ok' });

    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 5, pattern: 'a', is_regex: false, test_mode: false },
        { id: 6, pattern: 'b', is_regex: false, test_mode: false },
      ] as Entry[]);
  });

  it('commitEdit cancels when editing id not found in entries', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 1, pattern: 'one', is_regex: false }] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;
    comp.editingId = 999; // not in entries
    comp.editValue = 'two';
    comp.commitEdit();

    // No PUT should be issued
    httpMock.expectNone(
      (r) => r.method === 'PUT' && r.url.startsWith('/addresses/'),
    );
  });
});
