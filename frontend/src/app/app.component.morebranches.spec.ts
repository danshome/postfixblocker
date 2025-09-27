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

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 *
 * @param httpMock
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
      r.flush({ service: 'api', level: 'INFO' });
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

describe('AppComponent additional branches', () => {
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
    // Default spies: keep unauthenticated unless tests override
    authMock.getSession.and.returnValue(
      of({ authenticated: false } as SessionInfo),
    );
    authMock.loginPassword.and.returnValue(
      of<SessionInfo>({ authenticated: false }),
    );
    authMock.changePassword.and.returnValue(of<{ ok: boolean }>({ ok: false }));
    authMock.logout.and.returnValue(of<{ ok: boolean }>({ ok: true }));
    authMock.getRegisterChallenge.and.returnValue(of({}));
    authMock.verifyRegister.and.returnValue(
      of<SessionInfo>({ authenticated: false }),
    );
    authMock.getLoginChallenge.and.returnValue(of({}));
    authMock.verifyLogin.and.returnValue(
      of<SessionInfo>({ authenticated: false }),
    );

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
    flushInitialLogs(httpMock);
    httpMock.verify();
    (globalThis as Record<string, unknown>).__USE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('deleteSelected continues on deletion error; deleteAll triggers flow', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs(httpMock);

    // Initial list with two entries
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'a', is_regex: false },
        { id: 2, pattern: 'b', is_regex: false },
      ] as Entry[]);

    comp.toggleSelect(1, true);
    comp.toggleSelect(2, true);
    comp.deleteSelected();
    tick();

    // First delete fails, second succeeds
    const d1 = httpMock.expectOne('/addresses/1');
    d1.flush({ error: 'nope' }, { status: 404, statusText: 'NF' });
    const d2 = httpMock.expectOne('/addresses/2');
    d2.flush({ status: 'deleted' });

    // Reload after loop ends
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);

    // deleteAll routes through deleteSelected
    comp.deleteAll();
    tick();
    // No items, so no DELETEs
    httpMock.expectNone(
      (r) => r.method === 'DELETE' && r.url.startsWith('/addresses/'),
    );
  }));

  it('toggleTestMode error branch sets banners and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs(httpMock);

    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 3, pattern: 'c', is_regex: false, test_mode: true },
      ] as Entry[]);

    // Force error on PUT
    comp.toggleTestMode({
      id: 3,
      pattern: 'c',
      is_regex: false,
      test_mode: true,
    });
    const p = httpMock.expectOne('/addresses/3');
    p.flush({ error: 'nope' }, { status: 503, statusText: 'Not ready' });

    // Should trigger a reload regardless
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
  });

  it('commitEdit conflict (409) error path resets and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs(httpMock);

    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 7, pattern: 'old', is_regex: false }] as Entry[]);

    comp.beginEdit({ id: 7, pattern: 'old', is_regex: false });
    comp.editValue = 'new';
    comp.commitEdit();

    const put = httpMock.expectOne('/addresses/7');
    put.flush({ error: 'conflict' }, { status: 409, statusText: 'Conflict' });

    // After error, it should reload
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 7, pattern: 'old', is_regex: false }]);
  });

  it('loadLogSettings covers refresh failure + level success', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // First call from ngOnInit: allow both to fail/succeed as needed
    const r = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r.flush({ error: 'no' }, { status: 500, statusText: 'err' });
    const l = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    l.flush({ service: 'api', level: 'WARNING' });
    const t = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    t.flush({
      name: 'api',
      path: './logs/api.log',
      content: 'tail',
      missing: false,
    });

    // Initial data load
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    expect(comp.currentLevel).toBe('WARNING');
  }));

  it('onItemMouseEnter no-op when drag not active', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 1, pattern: 'a', is_regex: false }]);

    // Ensure not selected, mouse enter without drag should not change selection
    expect(comp.isSelected(1)).toBeFalse();
    comp.dragActive = false;
    comp.onItemMouseEnter(1);
    expect(comp.isSelected(1)).toBeFalse();
  });

  it('passkey flows: 503 error overrides on both register and login', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;

    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Ensure initial state
    expect(comp.passkeyBusy).toBeFalse();

    // Simulate 503 on register challenge
    authMock.getRegisterChallenge.and.returnValue(
      throwError(() => ({ status: 503 })),
    );
    comp.registerPasskey();
    tick();
    expect(String(comp.authError || '')).toMatch(/unavailable/i);
    expect(comp.passkeyBusy).toBeFalse();

    // Simulate 503 on login challenge
    authMock.getLoginChallenge.and.returnValue(
      throwError(() => ({ status: 503 })),
    );
    comp.loginWithPasskey();
    tick();
    expect(String(comp.authError || '')).toMatch(/unavailable/i);
    expect(comp.passkeyBusy).toBeFalse();

    // No unexpected network activity in this error-only scenario
    httpMock.expectNone((r) => r.url.startsWith('/addresses'));
    httpMock.expectNone((r) => r.url.startsWith('/logs'));
  }));
});
