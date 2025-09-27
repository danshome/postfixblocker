import { provideHttpClient } from '@angular/common/http';
import type { HttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import type { PageEvent } from '@angular/material/paginator';
import type { Sort } from '@angular/material/sort';
import { of } from 'rxjs';

import { AppComponent } from './app.component';
import { AppLogicService } from './app-logic.service';
import { AuthService } from './auth.service';
import { LoggerService } from './logger.service';
import { TimerService } from './timer.service';

interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

interface LiteHttp {
  post: jasmine.Spy;
  get: jasmine.Spy;
  put: jasmine.Spy;
  delete: jasmine.Spy;
}

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  /**
   *
   */
  function flushInitialLogs() {
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
          content: 'initial log content',
          missing: false,
        });
      }
    }
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      // Import standalone component and provide testing HttpClient/Noop animations
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
    // Drain any pending log-level/refresh requests before verification
    flushInitialLogs();
    httpMock.verify();
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('loads entries on init', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges(); // triggers ngOnInit -> load()

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    const data: Entry[] = [
      { id: 1, pattern: 'blocked@example.com', is_regex: false },
    ];
    request.flush(data);

    const comp = fixture.componentInstance;
    expect(comp.entries.length).toBe(1);
    expect(comp.entries[0].pattern).toBe('blocked@example.com');
  });

  it('adds an entry (via paste box) then reloads and resets form', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.bulkText = 'new@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    expect(post.request.method).toBe('POST');
    expect(post.request.body.pattern).toBe('new@example.com');
    expect(post.request.body.is_regex).toBe(false);
    post.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after add
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 2, pattern: 'new@example.com', is_regex: false }]);

    expect(comp.bulkText).toBe('');
    expect(comp.bulkIsRegex).toBe(false);
    expect(comp.entries.length).toBe(1);
  }));

  it('removes an entry then reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 5, pattern: 'x@y.com', is_regex: false }]);

    comp.remove(5);
    const del = httpMock.expectOne('/addresses/5');
    expect(del.request.method).toBe('DELETE');
    del.flush({ status: 'deleted' });

    // Reload after delete
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
    expect(comp.entries.length).toBe(0);
  });

  it('adds multiple entries from paste box (two lines) and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    // Initial GET
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.bulkText = 'a1@example.com\n a2@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post1 = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    expect(post1.request.method).toBe('POST');
    expect(post1.request.body.pattern).toBe('a1@example.com');
    expect(post1.request.body.is_regex).toBe(false);
    post1.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    tick();
    const post2 = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    expect(post2.request.method).toBe('POST');
    expect(post2.request.body.pattern).toBe('a2@example.com');
    expect(post2.request.body.is_regex).toBe(false);
    post2.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after bulk
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([
      { id: 1, pattern: 'a1@example.com', is_regex: false },
      { id: 2, pattern: 'a2@example.com', is_regex: false },
    ]);
    expect(comp.bulkText).toBe('');
    expect(comp.bulkIsRegex).toBe(false);
    expect(comp.entries.length).toBe(2);
  }));

  it('deletes selected entries then reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    // Initial GET with two entries
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 10, pattern: 's1@example.com', is_regex: false },
        { id: 11, pattern: 's2@example.com', is_regex: false },
      ]);

    // Select both and delete selected
    comp.toggleSelect(10, true);
    comp.toggleSelect(11, true);
    comp.deleteSelected();
    tick();

    const del1 = httpMock.expectOne(
      (request) =>
        request.method === 'DELETE' && request.url === '/addresses/10',
    );
    del1.flush({ status: 'deleted' });
    tick();
    const del2 = httpMock.expectOne(
      (request) =>
        request.method === 'DELETE' && request.url === '/addresses/11',
    );
    del2.flush({ status: 'deleted' });

    // Reload after deleteSelected
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);

    expect(comp.selected.size).toBe(0);
  }));

  it('filters entries locally', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 1, pattern: 'alpha@example.com', is_regex: false },
        { id: 2, pattern: 'beta@test.com', is_regex: true },
        { id: 3, pattern: 'gamma@foo.com', is_regex: false },
      ]);
    comp.localFilter = 'beta';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.map((entry) => entry.id)).toEqual([2]);

    comp.localFilter = 'YES'; // matches is_regex = true
    comp.applyLocalFilter();
    expect(comp.filteredEntries.map((entry) => entry.id)).toEqual([2]);

    comp.localFilter = '';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(3);
  });

  it('fetchTail updates content and handles error', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.logTab = 'api';
    comp.logLines = 123;
    comp.fetchTail();
    const t1 = httpMock.expectOne(
      (request) =>
        request.method === 'GET' &&
        request.url === '/logs/tail' &&
        request.params.get('name') === 'api' &&
        request.params.get('lines') === '123',
    );
    t1.flush({ content: 'hello' });
    expect(comp.logContent).toBe('hello');

    comp.fetchTail();
    const t2 = httpMock.expectOne(
      (request) => request.method === 'GET' && request.url === '/logs/tail',
    );
    t2.flush('err', { status: 500, statusText: 'Server Error' });
    expect(comp.logContent).toBe('');
  });

  it('saveLevel issues PUT for current tab', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.logTab = 'blocker';
    comp.currentLevel = 'DEBUG';
    comp.saveLevel();
    const put = httpMock.expectOne(
      (request) =>
        request.method === 'PUT' && request.url === '/logs/level/blocker',
    );
    expect(put.request.body).toEqual({ level: 'DEBUG' });
    put.flush({ status: 'ok' });
  });

  it('saveRefresh updates settings and starts timer to fetch tail', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    // Drain initial settings requests (they are sequential via awaits)
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.logTab = 'api';
    comp.refreshMs = 100;
    comp.logLines = 50;
    comp.saveRefresh();
    const put = httpMock.expectOne(
      (request) =>
        request.method === 'PUT' && request.url === '/logs/refresh/api',
    );
    expect(put.request.body).toEqual({ interval_ms: 100, lines: 50 });
    put.flush({ status: 'ok' });

    tick(110);
    // first interval fetch(es)
    let tails = httpMock.match(
      (request) => request.method === 'GET' && request.url === '/logs/tail',
    );
    expect(tails.length).toBeGreaterThan(0);
    tails[0].flush({ content: 'c1' });
    const rest1 = tails.slice(1);
    for (const t of rest1) {
      t.flush({ content: 'extra' });
    }

    tick(110);
    tails = httpMock.match(
      (request) => request.method === 'GET' && request.url === '/logs/tail',
    );
    expect(tails.length).toBeGreaterThan(0);
    tails[0].flush({ content: 'c2' });
    const rest2 = tails.slice(1);
    for (const t of rest2) {
      t.flush({ content: 'extra2' });
    }

    // stop timer to avoid leakage across tests
    comp.stopLogTimer();
  }));

  it('toggleSelectAll selects and clears', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.entries = [
      { id: 1, pattern: 'a', is_regex: false },
      { id: 2, pattern: 'b', is_regex: false },
    ];
    comp.toggleSelectAll(true);
    expect(comp.selected.size).toBe(2);
    comp.toggleSelectAll(false);
    expect(comp.selected.size).toBe(0);
  });

  it('row click toggles selection and suppressClick prevents double-toggle', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.entries = [{ id: 1, pattern: 'a', is_regex: false }];
    const mouseTarget = document.createElement('div');
    const event_ = {
      target: mouseTarget,
      preventDefault: (): void => {
        // Non-empty to satisfy lint; no side-effects needed for this test
        return undefined;
      },
    } as unknown as MouseEvent;
    comp.onItemMouseDown(1, event_);
    expect(comp.isSelected(1)).toBeTrue();
    // First click right after mousedown is suppressed
    comp.onItemClick(1, {
      target: document.createElement('div'),
    } as unknown as MouseEvent);
    expect(comp.isSelected(1)).toBeTrue();
    // Next click toggles off
    comp.onItemClick(1, {
      target: document.createElement('div'),
    } as unknown as MouseEvent);
    expect(comp.isSelected(1)).toBeFalse();
    comp.endDrag();
  });

  it('commitEdit success path updates entry and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 1, pattern: 'old', is_regex: false }]);

    comp.beginEdit({ id: 1, pattern: 'old', is_regex: false });
    comp.editValue = 'new';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (request) => request.method === 'PUT' && request.url === '/addresses/1',
    );
    expect(put.request.body).toEqual({ pattern: 'new' });
    put.flush({ status: 'ok' });

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 1, pattern: 'new', is_regex: false }]);
  });

  it('commitEdit fallback path posts new then deletes old and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 7, pattern: 'abc', is_regex: true }]);

    comp.beginEdit({ id: 7, pattern: 'abc', is_regex: true });
    comp.editValue = 'xyz';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (request) => request.method === 'PUT' && request.url === '/addresses/7',
    );
    put.flush('nope', { status: 404, statusText: 'Not Found' });

    const post = httpMock.expectOne(
      (request) => request.method === 'POST' && request.url === '/addresses',
    );
    expect(post.request.body).toEqual({ pattern: 'xyz', is_regex: true });
    post.flush({ id: 8, pattern: 'xyz', is_regex: true });

    const del = httpMock.expectOne(
      (request) =>
        request.method === 'DELETE' && request.url === '/addresses/7',
    );
    del.flush({ status: 'deleted' });

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 8, pattern: 'xyz', is_regex: true }]);
  });

  it('toggleTestMode flips a single entry and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 2, pattern: 'p', is_regex: false, test_mode: true }]);

    const entry = {
      id: 2,
      pattern: 'p',
      is_regex: false,
      test_mode: true,
    } as Entry;
    comp.toggleTestMode(entry);

    const put = httpMock.expectOne(
      (request) => request.method === 'PUT' && request.url === '/addresses/2',
    );
    expect(put.request.body).toEqual({ test_mode: false });
    put.flush({ status: 'ok' });

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 2, pattern: 'p', is_regex: false, test_mode: false }]);
  });

  it('setSelectedToTestMode updates selected entries and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 10, pattern: 'a', is_regex: false },
        { id: 11, pattern: 'b', is_regex: false },
      ]);

    comp.toggleSelect(10, true);
    comp.toggleSelect(11, true);
    comp.setSelectedToEnforceMode();
    tick();

    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/10',
      )
      .flush({ status: 'ok' });
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/11',
      )
      .flush({ status: 'ok' });

    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([
      { id: 10, pattern: 'a', is_regex: false },
      { id: 11, pattern: 'b', is_regex: false },
    ]);
    expect(comp.entries.length).toBe(2);
    expect(comp.busy).toBeFalse();
  }));

  it('setAllToTestMode updates every loaded entry and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 21, pattern: 'a', is_regex: false },
        { id: 22, pattern: 'b', is_regex: true },
      ]);

    comp.setAllToTestMode();
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/21',
      )
      .flush({ status: 'ok' });
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/22',
      )
      .flush({ status: 'ok' });
    tick();

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([
      { id: 21, pattern: 'a', is_regex: false },
      { id: 22, pattern: 'b', is_regex: true },
    ]);
    expect(comp.entries.length).toBe(2);
    expect(comp.busy).toBeFalse();
  }));

  it('setSelectedToTestMode updates selected entries and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 31, pattern: 'a', is_regex: false },
        { id: 32, pattern: 'b', is_regex: false },
      ]);

    comp.toggleSelect(31, true);
    comp.setSelectedToTestMode();
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/31',
      )
      .flush({ status: 'ok' });
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([
      { id: 31, pattern: 'a', is_regex: false },
      { id: 32, pattern: 'b', is_regex: false },
    ]);
    expect(comp.entries.length).toBe(2);
    expect(comp.busy).toBeFalse();
  }));

  it('setAllToEnforceMode updates every loaded entry and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 41, pattern: 'a', is_regex: false },
        { id: 42, pattern: 'b', is_regex: true },
      ]);

    comp.setAllToEnforceMode();
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/41',
      )
      .flush({ status: 'ok' });
    tick();
    httpMock
      .expectOne(
        (request) =>
          request.method === 'PUT' && request.url === '/addresses/42',
      )
      .flush({ status: 'ok' });
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([
      { id: 41, pattern: 'a', is_regex: false },
      { id: 42, pattern: 'b', is_regex: true },
    ]);
    expect(comp.entries.length).toBe(2);
    expect(comp.busy).toBeFalse();
  }));

  it('onPage and onSortChange trigger reload with new params', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.onPage({ pageIndex: 1, pageSize: 10, length: 0 } as PageEvent);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.onSortChange({ active: 'id', direction: 'desc' } as Sort);
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
    expect(comp.sortField).toBe('id');
    expect(comp.sortDir).toBe('desc');
    expect(comp.pageIndex).toBe(0);
  });

  it('onLogTabChange loads settings, tails, and starts timer', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    // Drain initial settings/tails (sequential via awaits)
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.onLogTabChange('postfix');
    // Allow async method to issue its HTTP requests
    tick();

    // Flush any of the three requests irrespective of order
    const pending1 = httpMock.match(
      (request) =>
        (request.method === 'GET' && request.url === '/logs/refresh/postfix') ||
        (request.method === 'GET' && request.url === '/logs/level/postfix') ||
        (request.method === 'GET' &&
          request.url === '/logs/tail' &&
          request.params.get('name') === 'postfix'),
    );
    // Provide responses for settings first if present
    for (const r of pending1) {
      if (r.request.url === '/logs/refresh/postfix') {
        r.flush({ name: 'postfix', interval_ms: 50, lines: 100 });
      }
    }
    for (const r of pending1) {
      if (r.request.url === '/logs/level/postfix') {
        r.flush({ service: 'postfix', level: 'INFO' });
      }
    }
    for (const r of pending1) {
      if (r.request.url === '/logs/tail') {
        r.flush({ content: 'p0' });
      }
    }
    tick();
    expect(comp.logTab).toBe('postfix');
    expect(comp.refreshMs).toBe(50);
    expect(comp.logLines).toBe(100);

    tick(60);
    const tails = httpMock.match(
      (request) => request.method === 'GET' && request.url === '/logs/tail',
    );
    if (tails.length > 0) {
      tails[0].flush({ content: 'p1' });
      const rest = tails.slice(1);
      for (const t of rest) {
        t.flush({ content: 'extra' });
      }
    }

    comp.stopLogTimer();
  }));

  it('addBulk does nothing on empty input', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.bulkText = '  \n   ';
    comp.addBulk();
    httpMock.expectNone('/addresses'); // no POSTs
    expect(comp.entries.length).toBe(0);
  });

  it('setBackendStatusFromError sets flags for 503 and network error', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.setBackendStatusFromError({ status: 503 });
    expect(comp.backendNotReady).toBeTrue();
    expect(comp.backendUnreachable).toBeFalse();

    comp.setBackendStatusFromError({ status: 0 });
    expect(comp.backendUnreachable).toBeTrue();
  });

  it('onItemClick ignores clicks on buttons and checkboxes', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.entries = [{ id: 1, pattern: 'a', is_regex: false }];
    // Click within a button
    const button = document.createElement('button');
    const buttonChild = document.createElement('span');
    button.append(buttonChild);
    comp.onItemClick(1, { target: buttonChild } as unknown as MouseEvent);
    expect(comp.isSelected(1)).toBeFalse();
    // Click within a mat-checkbox
    const callback = document.createElement('mat-checkbox');
    const callbackChild = document.createElement('div');
    callback.append(callbackChild);
    comp.onItemClick(1, { target: callbackChild } as unknown as MouseEvent);
    expect(comp.isSelected(1)).toBeFalse();
  });

  it('loadLogSettings handles error for level', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    // Drain initial
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.loadLogSettings('api');
    tick();
    const reqs = httpMock.match(
      (request) =>
        request.method === 'GET' &&
        (request.url === '/logs/refresh/api' ||
          request.url === '/logs/level/api'),
    );
    for (const r of reqs) {
      if (r.request.url === '/logs/refresh/api') {
        r.flush({ name: 'api', interval_ms: 0, lines: 200 });
      }
    }
    for (const r of reqs) {
      if (r.request.url === '/logs/level/api') {
        r.flush('boom', { status: 500, statusText: 'Server Error' });
      }
    }
    tick();
    expect(comp.currentLevel).toBe('');
    // Ensure any timers are stopped to prevent interval leakage across tests
    comp.stopLogTimer();
  }));

  it('commitEdit no-op when empty or unchanged', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 9, pattern: 'keep', is_regex: false }]);

    // Empty pattern
    comp.beginEdit({ id: 9, pattern: 'keep', is_regex: false });
    comp.editValue = '  ';
    comp.commitEdit();
    // Unchanged
    comp.beginEdit({ id: 9, pattern: 'keep', is_regex: false });
    comp.editValue = 'keep';
    comp.commitEdit();

    // No HTTP update calls should have been made beyond initial GET
    httpMock.expectNone(
      (request) => request.method === 'PUT' && request.url === '/addresses/9',
    );
    expect(comp.editingId).toBeNull();
  });
  it('saveRefresh error does not crash', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.logTab = 'api';
    comp.refreshMs = 100;
    comp.logLines = 25;
    (fixture.componentInstance as AppComponent).saveRefresh();
    const put = httpMock.expectOne(
      (request) =>
        request.method === 'PUT' && request.url === '/logs/refresh/api',
    );
    put.flush('boom', { status: 500, statusText: 'Server Error' });

    tick(200);
    // Ensure any timers are stopped to prevent interval leakage across tests
    comp.stopLogTimer();
    expect(comp).toBeTruthy();
  }));

  it('onSortChange with empty direction returns early', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);

    comp.onSortChange({ active: 'pattern', direction: '' } as Sort);
    const reqs = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(reqs.length).toBe(0);
  });

  it('load handles object response with items and total', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush({
        items: [
          { id: 101, pattern: 'p1', is_regex: false },
          { id: 102, pattern: 'p2', is_regex: true },
        ],
        total: 2,
      });
    expect(comp.entries.length).toBe(2);
    expect(comp.total).toBe(2);
  });

  it('applyLocalFilter filters by id, pattern, and regex flag', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 201, pattern: 'alpha', is_regex: false },
        { id: 202, pattern: 'beta', is_regex: true },
      ]);
    // Filter by pattern
    const event_ = { target: { value: 'alp' } } as unknown as Event;
    comp.applyLocalFilter(event_);
    expect(comp.filteredEntries.map((entry: Entry) => entry.id)).toEqual([201]);
    // Filter by id
    comp.applyLocalFilter({ target: { value: '202' } } as unknown as Event);
    expect(comp.filteredEntries.map((entry: Entry) => entry.id)).toEqual([202]);
    // Filter by regex flag text 'yes'
    comp.applyLocalFilter({ target: { value: 'yes' } } as unknown as Event);
    expect(comp.filteredEntries.map((entry: Entry) => entry.id)).toEqual([202]);
    // Clear filter
    comp.applyLocalFilter({ target: { value: '' } } as unknown as Event);
    expect(comp.filteredEntries.length).toBe(2);
  });

  it('addBulk deduplicates patterns before POST', fakeAsync(() => {
    // Use a stubbed HttpClient to avoid incidental log requests interfering
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({ status: 'ok' })),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.bulkText = 'dup@example.com\ndup@example.com\nunique@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();
    // Two posts only, with deduplicated patterns
    expect(fakeHttp.post.calls.count()).toBe(2);
    const sent = fakeHttp.post.calls
      .all()
      .map(
        (invocation) =>
          (
            (invocation as unknown as { args: unknown[] }).args[1] as {
              pattern: string;
            }
          ).pattern,
      )
      .toSorted();
    expect(sent).toEqual(['dup@example.com', 'unique@example.com']);
    // Reload GET invoked once via load()
    expect(fakeHttp.get.calls.count()).toBe(1);
  }));

  it('applyLocalFilter without event uses stored filter', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 601, pattern: 'abc', is_regex: false },
        { id: 602, pattern: 'def', is_regex: false },
      ]);
    comp.localFilter = 'def';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.map((entry: Entry) => entry.id)).toEqual([602]);
  });

  it('onItemClick toggles selection on row click', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 901, pattern: 'a', is_regex: false }]);
    comp.onItemClick(901, {
      target: document.createElement('div'),
    } as unknown as MouseEvent);
    expect(comp.isSelected(901)).toBeTrue();
    comp.onItemClick(901, {
      target: document.createElement('div'),
    } as unknown as MouseEvent);
    expect(comp.isSelected(901)).toBeFalse();
  });

  it('onSortChange early return on empty direction', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
    comp.onSortChange({ active: 'pattern', direction: '' } as Sort);
    // No new GET should be issued
    const more = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(more.length).toBe(0);
  });

  it('onSortChange triggers load on valid direction', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
    comp.onSortChange({ active: 'pattern', direction: 'desc' } as Sort);
    expect(comp.sortField).toBe('pattern');
    expect(comp.sortDir).toBe('desc');
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    request.flush([]);
  });

  it('load marks backendNotReady on 503', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    request.flush('down', { status: 503, statusText: 'Service Unavailable' });
    expect(comp.backendNotReady).toBeTrue();
  });

  it('setSelectedToTestMode updates selected ids and reloads', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [
      { id: 1, pattern: 'a', is_regex: false },
      { id: 2, pattern: 'b', is_regex: false },
    ];
    comp.toggleSelect(1, true);
    comp.toggleSelect(2, true);
    comp.setSelectedToTestMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(2);
    const urls = fakeHttp.put.calls
      .all()
      .map((call) => (call as jasmine.CallInfo).args[0] as string)
      .toSorted();
    expect(urls).toEqual(['/addresses/1', '/addresses/2']);
    for (const c of fakeHttp.put.calls.all()) {
      expect(c.args[1]).toEqual({ test_mode: true });
    }
    expect(fakeHttp.get.calls.count()).toBe(1);
  }));

  it('commitEdit falls back to create+delete on 404', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 10, pattern: 'oldp', is_regex: false }]);
    comp.beginEdit({ id: 10, pattern: 'oldp', is_regex: false });
    comp.editValue = 'newp';
    comp.commitEdit();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/10',
    );
    put.flush('missing', { status: 404, statusText: 'Not Found' });
    // Fallback: POST new, then DELETE old, then reload
    const post = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    post.flush(
      { id: 11, pattern: 'newp', is_regex: false },
      { status: 201, statusText: 'Created' },
    );
    const del = httpMock.expectOne(
      (r) => r.method === 'DELETE' && r.url === '/addresses/10',
    );
    del.flush({});
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 11, pattern: 'newp', is_regex: false }]);
    expect(comp.savingEdit).toBeFalse();
  }));

  it('deleteSelected is a no-op when nothing selected', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
    comp.deleteSelected();
    tick();
    // No DELETEs should occur
    const dels = httpMock.match(
      (r) => r.method === 'DELETE' && r.url.startsWith('/addresses/'),
    );
    expect(dels.length).toBe(0);
  }));

  it('maybeStartLogTimer triggers tail fetch when enabled', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // Do not call detectChanges to avoid ngOnInit
    comp.refreshMs = 100;
    comp.maybeStartLogTimer();
    tick(120);
    const tails = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/logs/tail'),
    );
    expect(tails.length).toBe(1);
    tails[0].flush({
      name: 'api',
      path: './logs/api.log',
      content: '',
      missing: false,
    });
  }));

  it('setSelectedToEnforceMode updates selected ids and reloads', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [
      { id: 3, pattern: 'c', is_regex: false },
      { id: 4, pattern: 'd', is_regex: false },
    ];
    comp.toggleSelect(3, true);
    comp.toggleSelect(4, true);
    comp.setSelectedToEnforceMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(2);
    const bodies = fakeHttp.put.calls
      .all()
      .map((call) => (call as jasmine.CallInfo).args[1]);
    for (const b of bodies) expect(b).toEqual({ test_mode: false });
    expect(fakeHttp.get.calls.count()).toBe(1);
  }));

  it('setAllToTestMode updates all entries', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [
      { id: 7, pattern: 'g', is_regex: false },
      { id: 8, pattern: 'h', is_regex: false },
      { id: 9, pattern: 'i', is_regex: false },
    ];
    comp.setAllToTestMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(3);
    for (const c of fakeHttp.put.calls.all())
      expect(c.args[1]).toEqual({ test_mode: true });
    expect(fakeHttp.get.calls.count()).toBe(1);
  }));

  it('setAllToEnforceMode updates all entries', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [
      { id: 12, pattern: 'l', is_regex: false },
      { id: 13, pattern: 'm', is_regex: false },
    ];
    comp.setAllToEnforceMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(2);
    for (const c of fakeHttp.put.calls.all())
      expect(c.args[1]).toEqual({ test_mode: false });
    expect(fakeHttp.get.calls.count()).toBe(1);
  }));

  it('setSelectedToTestMode no-op when none selected', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [{ id: 100, pattern: 'x', is_regex: false }];
    comp.setSelectedToTestMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(0);
    expect(fakeHttp.get.calls.count()).toBe(0);
  }));

  it('setSelectedToEnforceMode no-op when none selected', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.entries = [{ id: 101, pattern: 'x', is_regex: false }];
    comp.setSelectedToEnforceMode();
    tick();
    expect(fakeHttp.put.calls.count()).toBe(0);
    expect(fakeHttp.get.calls.count()).toBe(0);
  }));

  it('drag selection supports deselect mode', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 41, pattern: 'a', is_regex: false },
        { id: 42, pattern: 'b', is_regex: false },
      ]);
    // Start with both selected
    comp.toggleSelect(41, true);
    comp.toggleSelect(42, true);
    // Start drag on a selected row -> deselect mode
    comp.onItemMouseDown(41, {
      target: document.createElement('div'),
      preventDefault: (): void => {
        // Non-empty to satisfy lint; no side-effects needed for this test
        return undefined;
      },
    } as unknown as MouseEvent);
    comp.onItemMouseEnter(42);
    comp.endDrag();
    expect(comp.isSelected(41)).toBeFalse();
    expect(comp.isSelected(42)).toBeFalse();
  });

  it('onItemMouseDown ignores button target', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 61, pattern: 'a', is_regex: false }]);
    comp.onItemMouseDown(61, {
      target: document.createElement('button'),
      preventDefault: (): void => {
        // Non-empty to satisfy lint; no side-effects needed for this test
        return undefined;
      },
    } as unknown as MouseEvent);
    expect(comp.isSelected(61)).toBeFalse();
  });

  it('onItemMouseEnter ignored when drag inactive', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 71, pattern: 'a', is_regex: false },
        { id: 72, pattern: 'b', is_regex: false },
      ]);
    comp.onItemMouseEnter(71);
    expect(comp.isSelected(71)).toBeFalse();
  });

  it('fetchTail success sets log content', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    comp.fetchTail();
    const tail = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/logs/tail'),
    );
    tail.flush({
      name: 'api',
      path: './logs/api.log',
      content: 'hello',
      missing: false,
    });
    expect(comp.logContent).toBe('hello');
  });

  it('onPage triggers reload and updates index', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([]);
    comp.onPage({ pageIndex: 1, pageSize: 25 } as unknown as PageEvent);
    expect(comp.pageIndex).toBe(1);
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    request.flush([]);
  });

  it('toggleSelectAll(false) clears selection', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 81, pattern: 'a', is_regex: false },
        { id: 82, pattern: 'b', is_regex: false },
      ]);
    comp.toggleSelectAll(true);
    expect(comp.selected.size).toBe(2);
    comp.toggleSelectAll(false);
    expect(comp.selected.size).toBe(0);
  });

  it('onItemClick suppression skips toggle and clears flag', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 91, pattern: 'a', is_regex: false }]);
    comp.suppressClick = true;
    comp.onItemClick(91, {
      target: document.createElement('div'),
    } as unknown as MouseEvent);
    expect(comp.isSelected(91)).toBeFalse();
    expect(comp.suppressClick).toBeFalse();
  });

  it('addBulk with empty text is a no-op', fakeAsync(() => {
    const fakeHttp: LiteHttp = {
      post: jasmine.createSpy('post').and.returnValue(of({})),
      get: jasmine
        .createSpy('get')
        .and.returnValue(of({ items: [], total: 0 })),
      put: jasmine.createSpy('put').and.returnValue(of({})),
      delete: jasmine.createSpy('delete').and.returnValue(of({})),
    };
    const comp = new AppComponent(
      fakeHttp as unknown as HttpClient,
      new AuthService(fakeHttp as unknown as HttpClient),
      new AppLogicService(),
      new TimerService(),
      new LoggerService(),
    ) as unknown as AppComponent;
    comp.bulkText = '   \n\n  ';
    comp.addBulk();
    tick();
    expect(fakeHttp.post.calls.count()).toBe(0);
    expect(fakeHttp.get.calls.count()).toBe(0);
  }));

  it('onItemClick ignores mat-checkbox targets', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 92, pattern: 'a', is_regex: false }]);
    const checkboxElement = document.createElement('mat-checkbox');
    comp.onItemClick(92, { target: checkboxElement } as unknown as MouseEvent);
    expect(comp.isSelected(92)).toBeFalse();
  });

  it('commitEdit early return when savingEdit is true', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    comp.entries = [{ id: 33, pattern: 'x', is_regex: false }];
    comp.editingId = 33;
    comp.editValue = 'y';
    comp.savingEdit = true;
    comp.commitEdit();
    const reqs = httpMock.match(() => true);
    expect(reqs.length).toBe(0);
  });

  it('commitEdit early return when no id', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    comp.entries = [{ id: 34, pattern: 'x', is_regex: false }];
    comp.editingId = undefined;
    comp.editValue = 'z';
    comp.commitEdit();
    const reqs = httpMock.match(() => true);
    expect(reqs.length).toBe(0);
  });

  it('commitEdit early return when entry missing', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    comp.entries = [{ id: 35, pattern: 'x', is_regex: false }];
    comp.editingId = 99; // not in entries
    comp.editValue = 'y';
    comp.commitEdit();
    const reqs = httpMock.match(() => true);
    expect(reqs.length).toBe(0);
  });

  it('load handles network error and marks backendUnreachable', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    const request = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    request.flush('down', { status: 0, statusText: 'Network Error' });
    expect(comp.backendUnreachable).toBeTrue();
    expect(comp.entries.length).toBe(0);
  });

  it('fetchTail error clears logContent', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // No detectChanges; call directly
    comp.fetchTail();
    const tail = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/logs/tail'),
    );
    tail.flush('err', { status: 500, statusText: 'Server Error' });
    expect(comp.logContent).toBe('');
  });

  it('saveLevel sends level to backend', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // Directly call without ngOnInit
    comp.currentLevel = 'WARNING';
    comp.saveLevel();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/level/api',
    );
    expect(put.request.body).toEqual({ level: 'WARNING' });
    put.flush({});
  });

  it('saveRefresh updates refresh settings', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    comp.refreshMs = 1000;
    comp.logLines = 500;
    comp.saveRefresh();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/logs/refresh/api',
    );
    expect(put.request.body).toEqual({ interval_ms: 1000, lines: 500 });
    put.flush({});
  });

  it('commitEdit fallback handles post error', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 21, pattern: 'a', is_regex: false }]);
    comp.beginEdit({ id: 21, pattern: 'a', is_regex: false });
    comp.editValue = 'b';
    comp.commitEdit();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/21',
    );
    put.flush('missing', { status: 404, statusText: 'Not Found' });
    const post = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    post.flush('busy', { status: 503, statusText: 'Service Unavailable' });
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 21, pattern: 'a', is_regex: false }]);
    expect(comp.savingEdit).toBeFalse();
  }));

  it('commitEdit fallback handles delete error', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 22, pattern: 'x', is_regex: false }]);
    comp.beginEdit({ id: 22, pattern: 'x', is_regex: false });
    comp.editValue = 'y';
    comp.commitEdit();
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/22',
    );
    put.flush('missing', { status: 404, statusText: 'Not Found' });
    const post = httpMock.expectOne(
      (r) => r.method === 'POST' && r.url === '/addresses',
    );
    post.flush(
      { id: 23, pattern: 'y', is_regex: false },
      { status: 201, statusText: 'Created' },
    );
    const del = httpMock.expectOne(
      (r) => r.method === 'DELETE' && r.url === '/addresses/22',
    );
    del.flush('busy', { status: 503, statusText: 'Service Unavailable' });
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 22, pattern: 'x', is_regex: false }]);
    expect(comp.savingEdit).toBeFalse();
  }));

  it('commitEdit no-op for empty or same value', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // No ngOnInit to avoid extra traffic
    comp.entries = [{ id: 55, pattern: 'old', is_regex: false }];
    comp.beginEdit({ id: 55, pattern: 'old', is_regex: false });
    comp.editValue = 'old';
    comp.commitEdit();
    // No HTTP calls should have been made
    const anyRequest = httpMock.match(() => true);
    expect(anyRequest.length).toBe(0);
    // Empty value no-op
    comp.beginEdit({ id: 55, pattern: 'old', is_regex: false });
    comp.editValue = '   ';
    comp.commitEdit();
    const anyRequest2 = httpMock.match(() => true);
    expect(anyRequest2.length).toBe(0);
  });

  it('toggleTestMode flips explicit false to true and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 701, pattern: 'z', is_regex: false, test_mode: false }]);
    const entry = {
      id: 701,
      pattern: 'z',
      is_regex: false,
      test_mode: false,
    } as unknown as Entry;
    comp.toggleTestMode(entry);
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/701',
    );
    expect(put.request.body).toEqual({ test_mode: true });
    put.flush({ status: 'ok' });
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
  });

  it('loadLogSettings handles refresh endpoint error (defaults preserved)', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // Drive via tab-change without running ngOnInit
    comp.onLogTabChange('api');
    // Refresh request may be scheduled on next tick
    let refreshList = httpMock.match(
      (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
    );
    if (refreshList.length === 0) {
      tick();
      refreshList = httpMock.match(
        (r) => r.method === 'GET' && r.url === '/logs/refresh/api',
      );
    }
    expect(refreshList.length).toBe(1);
    const refresh = refreshList[0];
    refresh.flush('err', { status: 500, statusText: 'Server Error' });
    // After refresh resolves, level request is issued (possibly next tick)
    tick();
    let levelList = httpMock.match(
      (r) => r.method === 'GET' && r.url === '/logs/level/api',
    );
    if (levelList.length === 0) {
      tick();
      levelList = httpMock.match(
        (r) => r.method === 'GET' && r.url === '/logs/level/api',
      );
    }
    expect(levelList.length).toBe(1);
    const level = levelList[0];
    level.flush({ service: 'api', level: 'INFO' });
    tick();
    expect(comp.refreshMs).toBe(0);
    expect(comp.logLines).toBe(200);
    expect(comp.currentLevel).toBe('INFO');
    // fetchTail also runs; flush it to keep test queue clean
    let tails = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/logs/tail'),
    );
    if (tails.length === 0) {
      tick();
      tails = httpMock.match(
        (r) => r.method === 'GET' && r.url.startsWith('/logs/tail'),
      );
    }
    expect(tails.length).toBe(1);
    const tail = tails[0];
    tail.flush({
      name: 'api',
      path: './logs/api.log',
      content: '',
      missing: false,
    });
  }));

  it('deleteAll selects all and deletes', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 301, pattern: 'a', is_regex: false },
        { id: 302, pattern: 'b', is_regex: false },
      ]);
    comp.deleteAll();
    tick();
    httpMock
      .expectOne((r) => r.method === 'DELETE' && r.url === '/addresses/301')
      .flush({ status: 'ok' });
    tick();
    httpMock
      .expectOne((r) => r.method === 'DELETE' && r.url === '/addresses/302')
      .flush({ status: 'ok' });
    tick();
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
    expect(comp.selected.size).toBe(0);
  }));

  it('toggleTestMode flips default (undefined) test_mode to false and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 401, pattern: 'x', is_regex: false }]);
    const entry = {
      id: 401,
      pattern: 'x',
      is_regex: false,
    } as unknown as Entry;
    comp.toggleTestMode(entry);
    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/401',
    );
    expect(put.request.body).toEqual({ test_mode: false });
    put.flush({ status: 'ok' });
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
  });

  it('drag selection: ignores button mousedown and toggles on drag across rows', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 501, pattern: 'a', is_regex: false },
        { id: 502, pattern: 'b', is_regex: false },
        { id: 503, pattern: 'c', is_regex: false },
      ]);
    // Ignore drag from button target
    comp.onItemMouseDown(501, {
      target: document.createElement('button'),
      preventDefault: (): void => {
        // Non-empty to satisfy lint rules; no side-effects needed here
        return undefined;
      },
    } as unknown as MouseEvent);
    expect(comp.isSelected(501)).toBeFalse();
    // Start drag from a non-button target
    comp.onItemMouseDown(501, {
      target: document.createElement('div'),
      preventDefault: (): void => {
        // Non-empty to satisfy lint rules; no side-effects needed here
        return undefined;
      },
    } as unknown as MouseEvent);
    // Drag over next row
    comp.onItemMouseEnter(502);
    expect(comp.isSelected(501)).toBeTrue();
    expect(comp.isSelected(502)).toBeTrue();
    // End drag; entering another row should not change selection
    comp.endDrag();
    comp.onItemMouseEnter(503);
    expect(comp.isSelected(503)).toBeFalse();
  });

  it('maybeStartLogTimer with zero refresh does nothing', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    // Avoid ngOnInit side-effects
    comp.refreshMs = 0;
    comp.maybeStartLogTimer();
    tick(300);
    const reqs = httpMock.match(
      (r) => r.method === 'GET' && r.url === '/logs/tail',
    );
    expect(reqs.length).toBe(0);
  }));

  it('deleteSelected continues on errors', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([
        { id: 100, pattern: 'a', is_regex: false },
        { id: 101, pattern: 'b', is_regex: false },
      ]);

    comp.toggleSelect(100, true);
    comp.toggleSelect(101, true);
    comp.deleteSelected();
    tick();

    httpMock
      .expectOne((r) => r.method === 'DELETE' && r.url === '/addresses/100')
      .flush('busy', { status: 503, statusText: 'Service Unavailable' });
    tick();
    // It should continue to the next deletion even after an error
    httpMock
      .expectOne((r) => r.method === 'DELETE' && r.url === '/addresses/101')
      .flush({ status: 'ok' });
    tick();

    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([]);
    expect(comp.entries.length).toBe(0);
  }));

  it('remove handles error (no reload on error)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 5, pattern: 'x', is_regex: false }]);

    comp.remove(5);
    const del = httpMock.expectOne(
      (r) => r.method === 'DELETE' && r.url === '/addresses/5',
    );
    del.flush('busy', { status: 503, statusText: 'Service Unavailable' });
    const further = httpMock.match(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    expect(further.length).toBe(0);
  });

  it('commitEdit other error path triggers reload', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as AppComponent;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock
      .expectOne((r) => r.method === 'GET' && r.url.startsWith('/addresses'))
      .flush([{ id: 33, pattern: 'old', is_regex: false }]);

    comp.beginEdit({ id: 33, pattern: 'old', is_regex: false });
    comp.editValue = 'conflict';
    comp.commitEdit();

    const put = httpMock.expectOne(
      (r) => r.method === 'PUT' && r.url === '/addresses/33',
    );
    put.flush('conflict', { status: 409, statusText: 'Conflict' });
    const reload = httpMock.expectOne(
      (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
    );
    reload.flush([{ id: 33, pattern: 'old', is_regex: false }]);
    expect(comp.entries[0].pattern).toBe('old');
  });
});
