import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 * Drain initial log-related HTTP requests to keep specs isolated.
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

describe('AppComponent extra branch coverage 2', () => {
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
    drainLogs(httpMock);
    httpMock.verify();
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('applyLocalFilter(event) reads input value branch', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'alpha@example.com', is_regex: false },
        { id: 2, pattern: 'beta@example.com', is_regex: true },
      ] as Entry[]);

    const input = document.createElement('input');
    input.value = 'beta';
    const event_ = new Event('keyup');
    Object.defineProperty(event_, 'target', { value: input });
    comp.applyLocalFilter(event_);
    expect(comp.filteredEntries.length).toBe(1);
    expect(comp.filteredEntries[0].id).toBe(2);
  });

  it('load() network error (status 0) sets unreachable banner', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Logs OK
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

    // /addresses network error
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.error(new ProgressEvent('error'), { status: 0, statusText: 'Network' });
    expect(comp.backendUnreachable).toBeTrue();
  });

  it('commitEdit fallback flows for 405 and 501 error statuses', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 9, pattern: 'old', is_regex: true }] as Entry[]);

    // 405
    comp.beginEdit({ id: 9, pattern: 'old', is_regex: true });
    comp.editValue = 'new-405';
    comp.commitEdit();
    const p405 = httpMock.expectOne('/addresses/9');
    p405.flush(
      { error: 'method' },
      { status: 405, statusText: 'Method Not Allowed' },
    );
    const post405 = httpMock.expectOne('/addresses');
    expect(post405.request.body.pattern).toBe('new-405');
    post405.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });
    const del405 = httpMock.expectOne('/addresses/9');
    del405.flush({ status: 'deleted' });
    const reload405 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload405.flush([{ id: 10, pattern: 'new-405', is_regex: true }]);

    // 501
    comp.beginEdit({ id: 10, pattern: 'new-405', is_regex: true });
    comp.editValue = 'new-501';
    comp.commitEdit();
    const p501 = httpMock.expectOne('/addresses/10');
    p501.flush(
      { error: 'nyi' },
      { status: 501, statusText: 'Not Implemented' },
    );
    const post501 = httpMock.expectOne('/addresses');
    expect(post501.request.body.pattern).toBe('new-501');
    post501.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });
    const del501 = httpMock.expectOne('/addresses/10');
    del501.flush({ status: 'deleted' });
    const reload501 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload501.flush([{ id: 11, pattern: 'new-501', is_regex: true }]);
  });

  it('toggleTestMode success (flip from true->false)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 77, pattern: 'x', is_regex: false, test_mode: true },
      ] as Entry[]);

    comp.toggleTestMode({
      id: 77,
      pattern: 'x',
      is_regex: false,
      test_mode: true,
    });
    const request = httpMock.expectOne('/addresses/77');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ test_mode: false });
    request.flush({ status: 'ok' });

    // Reload
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 77, pattern: 'x', is_regex: false, test_mode: false }]);
  });
});
