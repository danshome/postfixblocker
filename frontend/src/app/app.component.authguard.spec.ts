/* eslint-disable sonarjs/no-hardcoded-passwords -- Test includes credential-like strings in descriptions and inputs for clarity */
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import {
  fakeAsync,
  TestBed,
  tick,
  type ComponentFixture,
} from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

/**
 * Extract all text content from the root native element of a component fixture.
 * @param {ComponentFixture<AppComponent>} fixture - The component fixture to read from.
 * @returns {string} The concatenated text content.
 */
function textContent(fixture: ComponentFixture<AppComponent>): string {
  return (fixture.nativeElement as HTMLElement).textContent || '';
}

describe('AppComponent auth gating of main content', () => {
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
    // Drain any pending HTTP calls to avoid leaks between specs
    const reqs = httpMock.match(() => true);
    for (const r of reqs) {
      if (
        r.request.method === 'GET' &&
        r.request.url.startsWith('/logs/refresh/')
      ) {
        r.flush({ name: 'api', interval_ms: 0, lines: 200 });
      } else if (
        r.request.method === 'GET' &&
        r.request.url.startsWith('/logs/level/')
      ) {
        r.flush({ service: 'api', level: undefined });
      } else if (
        r.request.method === 'GET' &&
        r.request.url.startsWith('/logs/tail')
      ) {
        r.flush({
          name: 'api',
          path: './logs/api.log',
          content: '',
          missing: false,
        });
      } else if (
        r.request.method === 'GET' &&
        r.request.url.startsWith('/addresses')
      ) {
        r.flush([]);
      } else if (
        r.request.method === 'POST' &&
        r.request.url === '/auth/logout'
      ) {
        r.flush({ ok: true });
      } else if (
        r.request.method === 'GET' &&
        (r.request.url === '/auth/session' || r.request.url === '/auth/me')
      ) {
        r.flush({ authenticated: false });
      } else {
        // For safety, fall back to a 200 empty response
        r.flush({});
      }
    }
    httpMock.verify();
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = undefined;
    expect().nothing();
  });

  it('hides all main content when unauthenticated, showing only Account card', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // Initial strict session check
    const s1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s1.flush({ authenticated: false });

    fixture.detectChanges();
    const html = textContent(fixture);
    expect(html).toContain('Account');
    expect(html).toContain('Sign in');
    // Main content titles should be hidden
    expect(html).not.toContain('Add Addresses');
    expect(html).not.toContain('Block List');
    expect(html).not.toContain('Logs');
  });

  it('shows main content once authenticated and no password change required', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    tick();

    // Initial session -> authenticated
    const s1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s1.flush({
      authenticated: true,
      username: 'admin',
      mustChangePassword: false,
    });
    tick();

    fixture.detectChanges();
    tick();

    // Expect log settings and tail, then addresses load
    const r1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r1.flush({ name: 'api', interval_ms: 0, lines: 200 });
    const l1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    l1.flush({ service: 'api', level: 'INFO' });
    const t1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    t1.flush({
      name: 'api',
      path: './logs/api.log',
      content: '',
      missing: false,
    });

    const getAddrs = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    getAddrs.flush([]);

    fixture.detectChanges();
    const html = textContent(fixture);
    expect(html).toContain('Add Addresses');
    expect(html).toContain('Block List');
    expect(html).toContain('Logs');
  }));

  it('keeps main content hidden when mustChangePassword=true', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    const s1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s1.flush({ authenticated: false });
    fixture.detectChanges();

    // Simulate login flow returning mustChangePassword
    const comp = fixture.componentInstance as AppComponent;
    comp.loginUsername = 'admin';
    comp.loginPassword = 'temp';
    const p = comp.loginWithPassword();

    const lp = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/auth/login/password',
    );
    lp.flush({
      authenticated: false,
      username: 'admin',
      mustChangePassword: true,
    });

    await p;
    fixture.detectChanges();
    const html = textContent(fixture);
    expect(html).toContain('You must change your password before continuing.');
    expect(html).not.toContain('Add Addresses');
    expect(html).not.toContain('Block List');
    expect(html).not.toContain('Logs');
  });
});
