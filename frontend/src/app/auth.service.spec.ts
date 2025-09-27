/* eslint-disable sonarjs/no-hardcoded-passwords -- Test uses fake credentials to validate payloads */
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import type { SessionInfo } from './auth.service';
import { AuthService } from './auth.service';
import type {
  RegistrationResponseJSON,
  AuthenticationResponseJSON,
} from '@simplewebauthn/browser';

describe('AuthService', () => {
  let svc: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    svc = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('getSession returns backend value when available', (done) => {
    const expectSess: SessionInfo = {
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
      hasWebAuthn: false,
    };
    svc.getSession().subscribe((value) => {
      expect(value).toEqual(expectSess);
      done();
    });
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    expect(request.request.withCredentials).toBeTrue();
    request.flush(expectSess);
  });

  it('getSession falls back to authenticated:true on error', (done) => {
    svc.getSession().subscribe((value) => {
      expect(value).toEqual({ authenticated: true });
      done();
    });
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ error: 'nope' }, { status: 404, statusText: 'Not Found' });
  });

  it('loginPassword posts username/password with credentials', () => {
    svc.loginPassword('admin', 'secret').subscribe();
    const request = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/login/password',
    );
    expect(request.request.body).toEqual({
      username: 'admin',
      password: 'secret',
    });
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ authenticated: true, username: 'admin' } as SessionInfo);
  });

  it('changePassword posts payload with credentials', () => {
    svc.changePassword('old', 'new').subscribe();
    const request = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/change-password',
    );
    expect(request.request.body).toEqual({
      old_password: 'old',
      new_password: 'new',
    });
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ ok: true });
  });

  it('logout posts empty body with credentials', () => {
    svc.logout().subscribe();
    const request = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/logout',
    );
    expect(request.request.body).toEqual({});
    expect(request.request.withCredentials).toBeTrue();
    request.flush({ ok: true });
  });

  it('register challenge and verify use credentials', () => {
    // challenge
    svc.getRegisterChallenge().subscribe();
    const c1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/register/challenge',
    );
    expect(c1.request.withCredentials).toBeTrue();
    c1.flush({});

    // verify
    const att = { id: 'cred' } as unknown as RegistrationResponseJSON;
    svc.verifyRegister(att).subscribe();
    const v1 = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/register/verify',
    );
    expect(v1.request.withCredentials).toBeTrue();
    expect(v1.request.body).toEqual(att);
    v1.flush({ authenticated: true } as SessionInfo);
  });

  it('login challenge and verify use credentials', () => {
    // challenge
    svc.getLoginChallenge().subscribe();
    const c1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/login/challenge',
    );
    expect(c1.request.withCredentials).toBeTrue();
    c1.flush({});

    // verify
    const asr = { id: 'assert' } as unknown as AuthenticationResponseJSON;
    svc.verifyLogin(asr).subscribe();
    const v1 = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/login/verify',
    );
    expect(v1.request.withCredentials).toBeTrue();
    expect(v1.request.body).toEqual(asr);
    v1.flush({ authenticated: true } as SessionInfo);
  });
});
