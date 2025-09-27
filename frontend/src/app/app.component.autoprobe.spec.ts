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

describe('AppComponent auto-probe auth (window.__PROBE_AUTH__)', () => {
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
    // Opt-in to auth probe while keeping __USE_AUTH__ undefined
    (globalThis as { __PROBE_AUTH__?: boolean }).__PROBE_AUTH__ = true;
  });

  afterEach(() => {
    // Drain any strays to avoid cross-spec interference
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
      } else {
        r.flush({});
      }
    }
    httpMock.verify();
    (globalThis as { __PROBE_AUTH__?: boolean }).__PROBE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation
    expect().nothing();
  });

  it('probes /auth/session when not using auth, then enables auth UI without loading data', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    // Allow ngOnInit async probe to subscribe
    tick();

    // First probe (auto-detect path)
    const s1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s1.flush({ authenticated: false });
    tick();

    // Once useAuth flips to true, ngOnInit performs a strict session check again
    const s2 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    s2.flush({ authenticated: false });
    tick();

    // No addresses or logs should be loaded until authenticated
    const stray = httpMock.match(
      (r) => r.url.startsWith('/addresses') || r.url.startsWith('/logs/'),
    );
    expect(stray.length).toBe(0);

    fixture.detectChanges();
    const html = textContent(fixture);
    expect(html).toContain('Account');
    expect(html).toContain('Sign in');
  }));
});
