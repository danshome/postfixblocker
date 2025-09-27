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
 * Drain only initial log requests to avoid interference; leave /addresses for assertions.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainInitial(httpMock: HttpTestingController) {
  // Drain only initial log requests to avoid interference; leave /addresses for the test to assert.
  for (let index = 0; index < 2; index++) {
    const reqs = httpMock.match(
      (r) =>
        r.method === 'GET' &&
        (r.url.startsWith('/logs/refresh/') ||
          r.url.startsWith('/logs/level/') ||
          r.url.startsWith('/logs/tail')),
    );
    if (reqs.length === 0) break;
    for (const r of reqs) {
      if (r.request.url.startsWith('/logs/refresh/')) {
        r.flush({ name: 'api', interval_ms: 0, lines: 200 });
      } else if (r.request.url.startsWith('/logs/level/')) {
        r.flush({ service: 'api', level: undefined });
      } else if (r.request.url.startsWith('/logs/tail')) {
        r.flush({
          name: 'api',
          path: './logs/api.log',
          content: '',
          missing: false,
        });
      }
    }
  }
}

describe('AppComponent extra branches 7', () => {
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
    // Drain any stray requests to keep specs isolated
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
    // Ensure at least one explicit expectation to satisfy jasmine
    expect().nothing();
  });

  it('onSortChange ignores empty direction (no reload)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    drainInitial(httpMock);
    // First data load
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    // Call with empty direction -> should not trigger a new GET
    comp.onSortChange({ active: 'id', direction: '' } as Sort);
    httpMock.expectNone(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
  });

  it('deleteSelected early return when selection is empty', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    // Nothing selected -> no DELETE should be sent
    await comp.deleteSelected();
    httpMock.expectNone(
      (r) => r.method === 'DELETE' && r.url.startsWith('/addresses/'),
    );
  });

  it('addBulk early return on empty/whitespace input', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    drainInitial(httpMock);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.bulkText = ' \n  ';
    comp.bulkIsRegex = true;
    await comp.addBulk();
    // No POSTs should be issued
    httpMock.expectNone((r) => r.method === 'POST' && r.url === '/addresses');
  });

  it('toggleSelectAll adds and clears selection', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Seed entries
    drainInitial(httpMock);
    const get = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    get.flush([
      { id: 1, pattern: 'a', is_regex: false },
      { id: 2, pattern: 'b', is_regex: true },
    ] as Entry[]);

    // Add all
    comp.toggleSelectAll(true);
    expect(comp.selected.size).toBe(2);
    expect(comp.isSelected(1)).toBeTrue();
    expect(comp.isSelected(2)).toBeTrue();

    // Clear all
    comp.toggleSelectAll(false);
    expect(comp.selected.size).toBe(0);
  });

  it('fetchTail omitNameParam excludes name query parameter', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();

    // Initial logs
    const r1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    r1.flush({ name: 'api', interval_ms: 0, lines: 200 });
    const l1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    l1.flush({ service: 'api', level: 'INFO' });
    // First tail (from ngOnInit)
    const t1 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    t1.flush({
      name: 'api',
      path: './logs/api.log',
      content: 'init',
      missing: false,
    });

    // Explicit fetch with omitNameParam=true should not include name param
    comp.fetchTail(undefined, true);
    const t2 = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    expect(t2.request.params.has('name')).toBeFalse();
    t2.flush({
      name: 'api',
      path: './logs/api.log',
      content: 'ok',
      missing: false,
    });
  });
});
