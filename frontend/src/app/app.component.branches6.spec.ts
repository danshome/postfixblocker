import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

/**
 * Drain and flush pending log/tail requests to avoid cross-spec interference.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainTail(httpMock: HttpTestingController) {
  const tails = httpMock.match(
    (r) => r.method === 'GET' && r.url === '/logs/tail',
  );
  for (const t of tails) {
    t.flush({
      name: 'api',
      path: './logs/api.log',
      content: '',
      missing: false,
    });
  }
}

describe('AppComponent extra branches 6 (level error path)', () => {
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
    // Drain any pending logs/addresses to avoid leaks
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
      } else {
        r.flush({});
      }
    }
    httpMock.verify();
    expect().nothing();
  });

  it('handles branch where refresh succeeds and level fails (sets currentLevel="")', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // Initial ngOnInit will request /logs/refresh/api and /logs/level/api and issue a tail.
    const r1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r1.flush({ name: 'api', interval_ms: 0, lines: 200 });
    const l1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    // Simulate failure for level endpoint to take error branch
    l1.flush({ error: 'err' }, { status: 500, statusText: 'Server' });
    // Tail issued immediately by component
    drainTail(httpMock);

    const comp = fixture.componentInstance as AppComponent;
    expect(comp.currentLevel).toBe('');
  });
});
