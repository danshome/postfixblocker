import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import type { Sort } from '@angular/material/sort';

import { AppComponent } from './app.component';

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

/**
 * Drain any initial log requests if they were fired to keep auth-focused specs isolated.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function flushInitialLogs(httpMock: HttpTestingController) {
  // Drain any initial log requests if they were fired
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
      r.flush({ service: 'api', level: undefined });
    } else if (url.startsWith('/logs/tail')) {
      r.flush({
        name: 'api',
        path: './logs/api.log',
        content: 'initial',
        missing: false,
      });
    }
  }
}

describe('AppComponent edit/auth branches', () => {
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
    flushInitialLogs(httpMock);
    httpMock.verify();
    // Reset auth gate flag between tests
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = undefined;
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('ngOnInit short-circuits when useAuth=true and not authenticated', () => {
    (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ = true;
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    // Expect only session check; no logs/addresses should be requested
    const sess = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/auth/session',
    );
    sess.flush({ authenticated: false, username: '' });

    // Ensure that no addresses request was fired
    const stray = httpMock.match((r) => r.url.startsWith('/addresses'));
    expect(stray.length).toBe(0);
  });

  it('onSortChange no-op when empty direction', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance;
    comp.onSortChange({ active: 'pattern', direction: '' } as Sort);

    // No new GET should be triggered
    const stray = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(stray.length).toBe(0);
  });

  it('fetchTail handles error path by clearing content', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    const comp = fixture.componentInstance;
    comp.logTab = 'api';
    comp.logLines = 100;
    comp.fetchTail();
    const tail = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    expect(tail.request.params.get('name')).toBe('api');
    tail.flush({ error: 'fail' }, { status: 500, statusText: 'Server Error' });
    expect(comp.logContent).toBe('');
  });

  it('commitEdit early-return paths (savingEdit true, no id, unchanged)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 10, pattern: 'a@example.com', is_regex: false },
      ] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;

    // savingEdit true -> immediate return
    comp.savingEdit = true;
    comp.commitEdit();
    comp.savingEdit = false;

    // no editingId -> immediate return
    comp.editingId = undefined;
    comp.commitEdit();

    // unchanged value -> cancel edit
    comp.beginEdit({
      id: 10,
      pattern: 'a@example.com',
      is_regex: false,
    } as Entry);
    comp.editValue = 'a@example.com';
    comp.commitEdit();

    // No HTTP beyond the initial GET
    const stray = httpMock.match(
      (r) => r.method !== 'GET' || !r.url.startsWith('/addresses'),
    );
    expect(stray.length).toBe(0);
  });

  it('commitEdit success PUT updates entry and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'old@example.com', is_regex: false },
      ] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;
    comp.beginEdit({
      id: 1,
      pattern: 'old@example.com',
      is_regex: false,
    } as Entry);
    comp.editValue = 'new@example.com';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/1',
    );
    expect(put.request.body).toEqual({ pattern: 'new@example.com' });
    put.flush({ status: 'ok' });

    // Reload
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 1, pattern: 'new@example.com', is_regex: false }]);
  });

  it('commitEdit 404 fallback: POST new then DELETE old then reload', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 2, pattern: 'old2@example.com', is_regex: true },
      ] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;
    comp.beginEdit({
      id: 2,
      pattern: 'old2@example.com',
      is_regex: true,
    } as Entry);
    comp.editValue = 'new2@example.com';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/2',
    );
    put.flush({ error: 'nope' }, { status: 404, statusText: 'Not Found' });

    const post = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    expect(post.request.body).toEqual({
      pattern: 'new2@example.com',
      is_regex: true,
    });
    post.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    const del = httpMock.expectOne(
      (r) => r.method === 'DELETE' && r.url === '/addresses/2',
    );
    del.flush({ status: 'deleted' });

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 3, pattern: 'new2@example.com', is_regex: true }]);
  });

  it('commitEdit conflict/error path triggers reload (no fallback)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    flushInitialLogs(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 3, pattern: 'aa@example.com', is_regex: false },
      ] as Entry[]);

    const comp = fixture.componentInstance as AppComponent;
    comp.beginEdit({
      id: 3,
      pattern: 'aa@example.com',
      is_regex: false,
    } as Entry);
    comp.editValue = 'bb@example.com';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/3',
    );
    put.flush({ error: 'conflict' }, { status: 409, statusText: 'Conflict' });

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 3, pattern: 'aa@example.com', is_regex: false }]);
  });
});
