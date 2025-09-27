import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { of } from 'rxjs';

import { AppComponent } from './app.component';
import { AuthService } from './auth.service';
import type { SessionInfo } from './auth.service';
import type { PageEvent } from '@angular/material/paginator';

/**
 * Drain initial log-related HTTP requests to keep specs deterministic.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainLogs(httpMock: HttpTestingController) {
  const reqs = httpMock.match(
    (r) =>
      r.method === 'GET' &&
      (r.url.startsWith('/logs/refresh/') ||
        r.url.startsWith('/logs/level/') ||
        r.url.startsWith('/logs/tail')),
  );
  for (const r of reqs) {
    if (r.request.url.startsWith('/logs/refresh/'))
      r.flush({ name: 'api', interval_ms: 0, lines: 200 });
    else if (r.request.url.startsWith('/logs/level/'))
      r.flush({ service: 'api', level: 'INFO' });
    else
      r.flush({
        name: 'api',
        path: './logs/api.log',
        content: '',
        missing: false,
      });
  }
}

describe('AppComponent final branches', () => {
  let httpMock: HttpTestingController;
  let authMock: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authMock = jasmine.createSpyObj<AuthService>('AuthService', [
      'getSession',
      'loginPassword',
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
    drainLogs(httpMock);
    httpMock.verify();
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('loginWithPassword: mustChangePassword true does not proceed to load', () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(
      of({ authenticated: false } as SessionInfo),
    );
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    authMock.loginPassword.and.returnValue(
      of({ authenticated: false, mustChangePassword: true } as SessionInfo),
    );
    comp.loginWithPassword();

    // Should not trigger addresses load (await user action)
    httpMock.expectNone(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
  });

  it('loginWithPassword: malformed session triggers friendly error', fakeAsync(() => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    authMock.getSession.and.returnValue(
      of({ authenticated: false } as SessionInfo),
    );
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    authMock.loginPassword.and.returnValue(
      of({ foo: 'bar' } as unknown as SessionInfo),
    );
    comp.loginWithPassword();
    tick();
    expect(comp.authError).toMatch(/login failed/i);
  }));

  it('loadLogSettings: both refresh and level rejected -> defaults applied', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Initial data load happens first
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([]);

    // Then log settings requests
    const r = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r.flush({ error: 'x' }, { status: 500, statusText: 'err' });
    const l = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    l.flush({ error: 'y' }, { status: 500, statusText: 'err' });
    const t = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    t.flush({
      name: 'api',
      path: './logs/api.log',
      content: '',
      missing: false,
    });

    expect(comp.currentLevel).toBe('');
  });

  it('commitEdit early return when no editingId', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.editingId = undefined;
    comp.editValue = 'x';
    comp.commitEdit();
    // No PUT expected
    httpMock.expectNone(
      (r) => r.method === 'PUT' && r.url.startsWith('/addresses/'),
    );
  });

  it('onPage emits reload with new params', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.onPage({ pageIndex: 2, pageSize: 50, length: 0 } as PageEvent);
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(request.request.params.get('page')).toBe('3');
    expect(request.request.params.get('page_size')).toBe('50');
    request.flush([]);
  });
});
