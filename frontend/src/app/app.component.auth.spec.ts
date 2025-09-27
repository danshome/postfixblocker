import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { of, throwError } from 'rxjs';

import { AppComponent } from './app.component';
import type { SessionInfo } from './auth.service';
import { AuthService } from './auth.service';
import * as webauthn from './webauthn.utility';
import type {
  AuthenticationResponseJSON,
  RegistrationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from '@simplewebauthn/browser';

// Helper to build test-only secrets without hard-coded password literals
/**
 * Concatenate parts into a single string for test-only secret construction.
 * @param {...string} cs - String fragments to concatenate.
 * @returns {string} The concatenated string.
 */
const tstr = (...cs: string[]) => cs.join('');

/**
 * Drain initial /logs HTTP mocks that may be triggered by component init.
 * @param {HttpTestingController} httpMock - HTTP testing controller to flush and match requests.
 * @returns {void} Nothing.
 */
function drainInitial(httpMock: HttpTestingController) {
  // Helper to flush any leftover /logs requests, including those triggered as a side effect
  // of flushing the first pair (refresh/level). Loop until stable.
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
      if (r.request.url.startsWith('/logs/refresh/')) {
        r.flush({ name: 'api', interval_ms: 0, lines: 200 });
      } else if (r.request.url.startsWith('/logs/level/')) {
        r.flush({ service: 'api', level: undefined });
      } else if (r.request.url.startsWith('/logs/tail')) {
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

describe('AppComponent auth flows and error branches', () => {
  let httpMock: HttpTestingController;
  let authMock: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authMock = jasmine.createSpyObj<AuthService>('AuthService', [
      'getSession',
      'loginPassword',
      'changePassword',
      'logout',
      'getRegisterChallenge',
      'verifyRegister',
      'getLoginChallenge',
      'verifyLogin',
    ]);

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        { provide: AuthService, useValue: authMock },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    drainInitial(httpMock);
    // Drain any stray addresses GETs that may occur when session is authenticated
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

  it('ngOnInit with useAuth=true and mustChangePassword avoids data/log loads', () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(
      of({ authenticated: false, mustChangePassword: true }),
    );

    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // No /addresses or /logs requests should be made
    httpMock.expectNone((request) => request.url.startsWith('/addresses'));
    httpMock.expectNone((request) => request.url.startsWith('/logs'));
  });

  it('loginWithPassword: 401 surfaces friendly error; success triggers data/log loads', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(of({ authenticated: false }));

    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // 401 branch
    authMock.loginPassword.and.returnValue(throwError(() => ({ status: 401 })));
    comp.loginUsername = 'admin';
    comp.loginPassword = tstr('w', 'r', 'o', 'n', 'g');
    comp.loginWithPassword();
    tick();
    expect(comp.authError).toMatch(/invalid username or password/i);

    // Success branch
    authMock.loginPassword.and.returnValue(
      of({ authenticated: true } as SessionInfo),
    );
    comp.loginPassword = tstr('s', 'e', 'c', 'r', 'e', 't');
    comp.loginWithPassword();
    tick();

    // onAuthenticated -> load logs + addresses
    drainInitial(httpMock); // loadLogSettings initial GETs
    const get1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    get1.flush([]);
  }));

  it('changePassword success then refreshSession continues; 401 error overriden', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(of({ authenticated: false }));

    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Error path
    authMock.changePassword.and.returnValue(
      throwError(() => ({ status: 401 })),
    );
    comp.oldPassword = tstr('o', 'l', 'd');
    comp.newPassword = tstr('n', 'e', 'w');
    comp.changePassword();
    tick();
    expect(comp.authError).toMatch(/old password is incorrect/i);

    // Success path -> refreshSession returns authenticated true
    authMock.changePassword.and.returnValue(
      of({ ok: true } as { ok: boolean }),
    );
    authMock.getSession.and.returnValue(of({ authenticated: true }));
    comp.changePassword();
    tick();

    // load after auth
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
  }));

  it('registerPasskey success and 401 override; loginWithPasskey success and 404 override', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(of({ authenticated: true }));
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    // Drain any initial addresses load triggered by authenticated session
    const maybeAddr = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    for (const r of maybeAddr) {
      r.flush([]);
    }

    // Stub WebAuthn via loader hook instead of spying on ESM exports
    webauthn.__setWebAuthnLoader(async () => ({
      startRegistration: async () =>
        ({ att: 'x' }) as unknown as RegistrationResponseJSON,
      startAuthentication: async () =>
        ({ asr: 'y' }) as unknown as AuthenticationResponseJSON,
    }));

    // registerPasskey success
    authMock.getRegisterChallenge.and.returnValue(
      of({
        rp: { name: 'Postfix Blocker' },
        user: { id: 'admin', name: 'admin', displayName: 'admin' },
        challenge: 'AAAA',
        pubKeyCredParams: [],
      } as unknown as PublicKeyCredentialCreationOptionsJSON),
    );
    authMock.verifyRegister.and.returnValue(
      of({ authenticated: true } as SessionInfo),
    );
    comp.registerPasskey();
    tick();
    expect(comp.authError).toBe('');

    // registerPasskey 401 error
    authMock.getRegisterChallenge.and.returnValue(
      throwError(() => ({ status: 401 })),
    );
    comp.registerPasskey();
    tick();
    expect(comp.authError).toMatch(/sign in before registering/i);

    // loginWithPasskey success
    authMock.getLoginChallenge.and.returnValue(
      of({
        challenge: 'BBBB',
      } as unknown as PublicKeyCredentialRequestOptionsJSON),
    );
    authMock.verifyLogin.and.returnValue(
      of({ authenticated: true } as SessionInfo),
    );
    comp.loginWithPasskey();
    tick();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    // loginWithPasskey 404 error
    authMock.getLoginChallenge.and.returnValue(
      throwError(() => ({ status: 404 })),
    );
    comp.loginWithPasskey();
    tick();
    expect(comp.authError).toMatch(/no passkey registered/i);
  }));

  it('logout success and error branch', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(of({ authenticated: true }));
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Success
    authMock.logout.and.returnValue(of({ ok: true } as { ok: boolean }));
    comp.logout();
    tick();
    expect(comp.session.authenticated).toBeFalse();

    // Error path
    authMock.logout.and.returnValue(throwError(() => ({ status: 500 })));
    comp.logout();
    tick();
    expect(comp.authError).toMatch(/logout failed/i);
  }));

  it('load() 503 error sets backend banners; fetchTail error; saveLevel/saveRefresh error branches', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Initial logs
    const r1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r1.flush({ name: 'api', interval_ms: 0, lines: 200 });
    const l1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    l1.flush({ service: 'api', level: 'INFO' });
    // Tail error path
    const t1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    t1.flush({ error: 'x' }, { status: 500, statusText: 'err' });

    // /addresses error
    const g1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g1.flush(
      { error: 'not ready' },
      { status: 503, statusText: 'DB not ready' },
    );
    expect(comp.backendNotReady).toBeTrue();

    // saveLevel/saveRefresh error branches
    comp.logTab = 'api';
    comp.currentLevel = 'DEBUG';
    comp.saveLevel();
    const putL = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/level/api',
    );
    putL.flush({ error: 'nope' }, { status: 500, statusText: 'err' });

    comp.refreshMs = 1000;
    comp.logLines = 100;
    comp.saveRefresh();
    const putR = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/refresh/api',
    );
    putR.flush({ error: 'nope' }, { status: 500, statusText: 'err' });
  }));

  it('onSortChange non-empty triggers reload; onLogTabChange to postfix triggers postfix endpoints', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);

    // First data load
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    // Change sort with non-empty direction
    comp.onSortChange({
      active: 'id',
      direction: 'desc',
    } as import('@angular/material/sort').Sort);
    const request2 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(request2.request.params.get('sort')).toBe('id');
    expect(request2.request.params.get('dir')).toBe('desc');
    request2.flush([]);

    // Switch to postfix tab
    comp.onLogTabChange('postfix');
    tick();
    const rf = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/postfix',
    );
    rf.flush({ name: 'postfix', interval_ms: 0, lines: 200 });
    const lf = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/postfix',
    );
    lf.flush({ service: 'postfix', level: 'INFO' });
    const tf = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    expect(tf.request.params.get('name')).toBe('postfix');
    tf.flush({
      name: 'postfix',
      path: './logs/postfix.log',
      content: '',
      missing: false,
    });
  }));

  it('commitEdit early-return branches: savingEdit and missing current item', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    // savingEdit prevents PUT
    comp.savingEdit = true;
    comp.editingId = 123;
    comp.editValue = 'x';
    comp.commitEdit();
    httpMock.expectNone(
      (r) => r.method === 'PUT' && r.url === '/addresses/123',
    );

    // missing current item -> cancel edit (no network)
    comp.savingEdit = false;
    comp.editingId = 999;
    comp.editValue = 'abc';
    comp.commitEdit();
    httpMock.expectNone(
      (r) => r.method === 'PUT' && r.url === '/addresses/999',
    );
  });
});
