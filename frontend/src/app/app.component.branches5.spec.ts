import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 * Drain initial log-related HTTP requests to prevent cross-spec leakage.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainInitial(httpMock: HttpTestingController) {
  const logs = httpMock.match(
    (r) =>
      r.method === 'GET' &&
      (r.url.startsWith('/logs/refresh/') ||
        r.url.startsWith('/logs/level/') ||
        r.url.startsWith('/logs/tail')),
  );
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

describe('AppComponent additional branches to reach 90%', () => {
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
    // Drain any stray addresses GETs to avoid cross-spec interference
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

  it('load() handles object response shape with items/total', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    const get = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    get.flush({ items: [{ id: 1, pattern: 'x', is_regex: false }], total: 1 });

    const comp = fixture.componentInstance as AppComponent;
    expect(comp.entries.length).toBe(1);
    expect(comp.total).toBe(1);
  });

  it('loadLogSettings covers branch where refresh fails and level succeeds', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // First, drain the initial api log settings and tail that ngOnInit issues
    const r1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r1.flush({ error: 'no' }, { status: 500, statusText: 'Server' });
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

    // Initial data load
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance as AppComponent;
    // Switch to postfix explicitly and load settings again; tick() to ensure requests are issued in fakeAsync
    comp.onLogTabChange('postfix');
    tick();

    // Expect requests for postfix
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/logs/refresh/postfix')
      .flush({ error: 'no' }, { status: 500, statusText: 'Server' });
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url === '/logs/level/postfix')
      .flush({ service: 'postfix', level: 'DEBUG' });
    const t2 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    // Ensure the name param is correctly set to postfix (but matcher above ignores params to be resilient)
    expect(t2.request.params.get('name')).toBe('postfix');
    t2.flush({
      name: 'postfix',
      path: './logs/postfix.log',
      content: 'ok',
      missing: false,
    });

    // After onLogTabChange, ensure component reflects received level
    expect(comp.currentLevel).toBe('DEBUG');
  }));

  it('toggleTestMode error branch triggers status and reload', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 10, pattern: 'a', is_regex: false, test_mode: true },
      ] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;
    comp.toggleTestMode({
      id: 10,
      pattern: 'a',
      is_regex: false,
      test_mode: true,
    });
    const put = httpMock.expectOne('/addresses/10');
    put.flush(
      { error: 'db not ready' },
      { status: 503, statusText: 'Unavailable' },
    );
    // backendNotReady should be set before reload
    expect(comp.backendNotReady).toBeTrue();
    // On error path, component will .load() afterward
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
  });
});
