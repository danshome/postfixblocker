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
 * Drain initial log requests for the API tab to prime the component under test.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainInitial(httpMock: HttpTestingController) {
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
}

/**
 * Drain and flush all pending HTTP requests to ensure isolation between specs.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainAll(httpMock: HttpTestingController) {
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
      r.flush({ service: 'api', level: 'INFO' });
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
}

describe('AppComponent extra branches 8', () => {
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
    drainAll(httpMock);
    httpMock.verify();
    // Ensure at least one explicit expectation to satisfy jasmine
    expect().nothing();
  });

  it('fetchTail early-exit when tailInFlight is true', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    // Initial data load
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([]);

    comp.tailInFlight = true;
    comp.fetchTail();
    // No new /logs/tail request should be issued
    httpMock.expectNone((r) => r.method === 'GET' && r.url === '/logs/tail');
  });

  it('applyLocalFilter without event uses existing localFilter', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([
      { id: 1, pattern: 'alpha@example.com', is_regex: false },
      { id: 2, pattern: 'beta@example.com', is_regex: true },
    ] as Entry[]);

    comp.localFilter = 'alpha';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(1);
    expect(comp.filteredEntries[0].id).toBe(1);
  });

  it('onItemMouseDown ignores when target is a button', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([{ id: 10, pattern: 'x', is_regex: false }] as Entry[]);

    const button = document.createElement('button');
    const event_ = new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
    });
    Object.defineProperty(event_, 'target', { value: button });

    comp.onItemMouseDown(10, event_ as MouseEvent);
    expect(comp.dragActive).toBeFalse();
    expect(comp.selected.size).toBe(0);
  });

  it('onItemClick ignores clicks on buttons', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([{ id: 20, pattern: 'y', is_regex: false }] as Entry[]);

    const button = document.createElement('button');
    const event_ = new MouseEvent('click', { bubbles: true, cancelable: true });
    Object.defineProperty(event_, 'target', { value: button });

    comp.onItemClick(20, event_ as MouseEvent);
    expect(comp.selected.size).toBe(0);
  });

  it('commitEdit early-returns when pattern is unchanged', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    drainInitial(httpMock);
    const g = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    g.flush([{ id: 30, pattern: 'same', is_regex: false }] as Entry[]);

    comp.beginEdit({ id: 30, pattern: 'same', is_regex: false });
    comp.editValue = 'same';
    comp.commitEdit();
    // No PUT should be issued for unchanged value
    httpMock.expectNone((r) => r.method === 'PUT' && r.url === '/addresses/30');
  });
});
