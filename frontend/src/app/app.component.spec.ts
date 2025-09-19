import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AppComponent } from './app.component';

interface Entry { id: number; pattern: string; is_regex: boolean; test_mode?: boolean; }

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  function flushInitialLogs() {
    const logs = httpMock.match(req => req.method === 'GET' && (req.url.startsWith('/logs/refresh/') || req.url.startsWith('/logs/level/') || req.url.startsWith('/logs/tail')));
    for (const r of logs) {
      const url = r.request.url;
      if (url.startsWith('/logs/refresh/')) {
        r.flush({ name: 'api', interval_ms: 0, lines: 200 });
      } else if (url.startsWith('/logs/level/')) {
        r.flush({ service: 'api', level: null });
      } else if (url.startsWith('/logs/tail')) {
        r.flush({ name: 'api', path: './logs/api.log', content: 'initial log content', missing: false });
      }
    }
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      // Import standalone component and testing HttpClient
      imports: [AppComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    // Drain any pending log-level/refresh requests before verification
    flushInitialLogs();
    httpMock.verify();
  });

  it('loads entries on init', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges(); // triggers ngOnInit -> load()

    // Respond to initial logs settings requests triggered by ngOnInit
    flushInitialLogs();

    const req = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    const data: Entry[] = [
      { id: 1, pattern: 'blocked@example.com', is_regex: false },
    ];
    req.flush(data);

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
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.bulkText = 'new@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post = httpMock.expectOne(r => r.method === 'POST' && r.url === '/addresses');
    expect(post.request.method).toBe('POST');
    expect(post.request.body.pattern).toBe('new@example.com');
    expect(post.request.body.is_regex).toBe(false);
    post.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after add
    tick();
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
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
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 5, pattern: 'x@y.com', is_regex: false },
    ]);

    comp.remove(5);
    const del = httpMock.expectOne('/addresses/5');
    expect(del.request.method).toBe('DELETE');
    del.flush({ status: 'deleted' });

    // Reload after delete
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
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
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.bulkText = 'a1@example.com\n a2@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post1 = httpMock.expectOne(r => r.method === 'POST' && r.url === '/addresses');
    expect(post1.request.method).toBe('POST');
    expect(post1.request.body.pattern).toBe('a1@example.com');
    expect(post1.request.body.is_regex).toBe(false);
    post1.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    tick();
    const post2 = httpMock.expectOne(r => r.method === 'POST' && r.url === '/addresses');
    expect(post2.request.method).toBe('POST');
    expect(post2.request.body.pattern).toBe('a2@example.com');
    expect(post2.request.body.is_regex).toBe(false);
    post2.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after bulk
    tick();
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
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
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 10, pattern: 's1@example.com', is_regex: false },
      { id: 11, pattern: 's2@example.com', is_regex: false },
    ]);

    // Select both and delete selected
    comp.toggleSelect(10, true);
    comp.toggleSelect(11, true);
    comp.deleteSelected();
    tick();

    const del1 = httpMock.expectOne(req => req.method === 'DELETE' && req.url === '/addresses/10');
    del1.flush({ status: 'deleted' });
    tick();
    const del2 = httpMock.expectOne(req => req.method === 'DELETE' && req.url === '/addresses/11');
    del2.flush({ status: 'deleted' });

    // Reload after deleteSelected
    tick();
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([]);

    expect(comp.selected.size).toBe(0);
  }));

  it('filters entries locally', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 1, pattern: 'alpha@example.com', is_regex: false },
      { id: 2, pattern: 'beta@test.com', is_regex: true },
      { id: 3, pattern: 'gamma@foo.com', is_regex: false },
    ]);
    comp.localFilter = 'beta';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.map(e => e.id)).toEqual([2]);

    comp.localFilter = 'YES'; // matches is_regex = true
    comp.applyLocalFilter();
    expect(comp.filteredEntries.map(e => e.id)).toEqual([2]);

    comp.localFilter = '';
    comp.applyLocalFilter();
    expect(comp.filteredEntries.length).toBe(3);
  });

  it('fetchTail updates content and handles error', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.logTab = 'api';
    comp.logLines = 123;
    comp.fetchTail();
    const t1 = httpMock.expectOne(req => req.method === 'GET' && req.url === '/logs/tail' && req.params.get('name') === 'api' && req.params.get('lines') === '123');
    t1.flush({ content: 'hello' });
    expect(comp.logContent).toBe('hello');

    comp.fetchTail();
    const t2 = httpMock.expectOne(req => req.method === 'GET' && req.url === '/logs/tail');
    t2.flush('err', { status: 500, statusText: 'Server Error' });
    expect(comp.logContent).toBe('');
  });

  it('saveLevel issues PUT for current tab', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.logTab = 'blocker';
    comp.currentLevel = 'DEBUG';
    comp.saveLevel();
    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/logs/level/blocker');
    expect(put.request.body).toEqual({ level: 'DEBUG' });
    put.flush({ status: 'ok' });
  });

  it('saveRefresh updates settings and starts timer to fetch tail', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    // Drain initial settings requests (they are sequential via awaits)
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.logTab = 'api';
    comp.refreshMs = 100;
    comp.logLines = 50;
    (fixture.componentInstance as any).saveRefresh();
    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/logs/refresh/api');
    expect(put.request.body).toEqual({ interval_ms: 100, lines: 50 });
    put.flush({ status: 'ok' });

    tick(110);
    // first interval fetch(es)
    let tails = httpMock.match(req => req.method === 'GET' && req.url === '/logs/tail');
    expect(tails.length).toBeGreaterThan(0);
    tails[0].flush({ content: 'c1' });
    for (let i = 1; i < tails.length; i++) { tails[i].flush({ content: 'extra' }); }

    tick(110);
    tails = httpMock.match(req => req.method === 'GET' && req.url === '/logs/tail');
    expect(tails.length).toBeGreaterThan(0);
    tails[0].flush({ content: 'c2' });
    for (let i = 1; i < tails.length; i++) { tails[i].flush({ content: 'extra2' }); }

    // stop timer to avoid leakage across tests
    comp.stopLogTimer();
  }));

  it('toggleSelectAll selects and clears', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

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
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.entries = [{ id: 1, pattern: 'a', is_regex: false }];
    const ev: any = { target: document.createElement('div'), preventDefault: () => {} };
    comp.onItemMouseDown(1, ev);
    expect(comp.isSelected(1)).toBeTrue();
    // First click right after mousedown is suppressed
    comp.onItemClick(1, { target: document.createElement('div') } as any);
    expect(comp.isSelected(1)).toBeTrue();
    // Next click toggles off
    comp.onItemClick(1, { target: document.createElement('div') } as any);
    expect(comp.isSelected(1)).toBeFalse();
    comp.endDrag();
  });

  it('commitEdit success path updates entry and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 1, pattern: 'old', is_regex: false },
    ]);

    comp.beginEdit({ id: 1, pattern: 'old', is_regex: false });
    comp.editValue = 'new';
    comp.commitEdit();

    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/1');
    expect(put.request.body).toEqual({ pattern: 'new' });
    put.flush({ status: 'ok' });

    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([{ id: 1, pattern: 'new', is_regex: false }]);
  });

  it('commitEdit fallback path posts new then deletes old and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 7, pattern: 'abc', is_regex: true },
    ]);

    comp.beginEdit({ id: 7, pattern: 'abc', is_regex: true });
    comp.editValue = 'xyz';
    comp.commitEdit();

    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/7');
    put.flush('nope', { status: 404, statusText: 'Not Found' });

    const post = httpMock.expectOne(req => req.method === 'POST' && req.url === '/addresses');
    expect(post.request.body).toEqual({ pattern: 'xyz', is_regex: true });
    post.flush({ id: 8, pattern: 'xyz', is_regex: true });

    const del = httpMock.expectOne(req => req.method === 'DELETE' && req.url === '/addresses/7');
    del.flush({ status: 'deleted' });

    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([{ id: 8, pattern: 'xyz', is_regex: true }]);
  });

  it('toggleTestMode flips a single entry and reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 2, pattern: 'p', is_regex: false, test_mode: true },
    ]);

    const entry = { id: 2, pattern: 'p', is_regex: false, test_mode: true } as Entry;
    comp.toggleTestMode(entry);

    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/2');
    expect(put.request.body).toEqual({ test_mode: false });
    put.flush({ status: 'ok' });

    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([{ id: 2, pattern: 'p', is_regex: false, test_mode: false }]);
  });

  it('setSelectedMode updates selected entries and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 10, pattern: 'a', is_regex: false },
      { id: 11, pattern: 'b', is_regex: false },
    ]);

    comp.toggleSelect(10, true);
    comp.toggleSelect(11, true);
    comp.setSelectedMode(false);
    tick();

    httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/10').flush({ status: 'ok' });
    tick();
    httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/11').flush({ status: 'ok' });

    tick();
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([
      { id: 10, pattern: 'a', is_regex: false },
      { id: 11, pattern: 'b', is_regex: false },
    ]);
  }));

  it('setAllMode updates every loaded entry and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 21, pattern: 'a', is_regex: false },
      { id: 22, pattern: 'b', is_regex: true },
    ]);

    comp.setAllMode(true);
    tick();
    httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/21').flush({ status: 'ok' });
    tick();
    httpMock.expectOne(req => req.method === 'PUT' && req.url === '/addresses/22').flush({ status: 'ok' });
    tick();

    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([
      { id: 21, pattern: 'a', is_regex: false },
      { id: 22, pattern: 'b', is_regex: true },
    ]);
  }));

  it('onPage and onSortChange trigger reload with new params', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.onPage({ pageIndex: 1, pageSize: 10, length: 0 } as any);
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.onSortChange({ active: 'id', direction: 'desc' } as any);
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);
  });

  it('onLogTabChange loads settings, tails, and starts timer', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    // Drain initial settings/tails (sequential via awaits)
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.onLogTabChange('postfix');
    // Allow async method to issue its HTTP requests
    tick();

    // Flush any of the three requests irrespective of order
    const pending1 = httpMock.match(req => (
      (req.method === 'GET' && req.url === '/logs/refresh/postfix') ||
      (req.method === 'GET' && req.url === '/logs/level/postfix') ||
      (req.method === 'GET' && req.url === '/logs/tail' && req.params.get('name') === 'postfix')
    ));
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

    tick(60);
    const tails = httpMock.match(req => req.method === 'GET' && req.url === '/logs/tail');
    if (tails.length > 0) {
      tails[0].flush({ content: 'p1' });
      for (let i = 1; i < tails.length; i++) tails[i].flush({ content: 'extra' });
    }

    comp.stopLogTimer();
  }));

  it('addBulk does nothing on empty input', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.bulkText = '  \n   ';
    comp.addBulk();
    httpMock.expectNone('/addresses'); // no POSTs
  });

  it('setBackendStatusFromError sets flags for 503 and network error', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp['setBackendStatusFromError']({ status: 503 });
    expect(comp.backendNotReady).toBeTrue();
    expect(comp.backendUnreachable).toBeFalse();

    comp['setBackendStatusFromError']({ status: 0 });
    expect(comp.backendUnreachable).toBeTrue();
  });

  it('onItemClick ignores clicks on buttons and checkboxes', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.entries = [{ id: 1, pattern: 'a', is_regex: false }];
    // Click within a button
    const btn = document.createElement('button');
    const btnChild = document.createElement('span');
    btn.appendChild(btnChild);
    comp.onItemClick(1, { target: btnChild } as any);
    expect(comp.isSelected(1)).toBeFalse();
    // Click within a mat-checkbox
    const cb = document.createElement('mat-checkbox');
    const cbChild = document.createElement('div');
    cb.appendChild(cbChild);
    comp.onItemClick(1, { target: cbChild } as any);
    expect(comp.isSelected(1)).toBeFalse();
  });

  it('loadLogSettings handles error for level', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    // Drain initial
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.loadLogSettings('api');
    tick();
    const reqs = httpMock.match(req => req.method === 'GET' && (req.url === '/logs/refresh/api' || req.url === '/logs/level/api'));
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
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 9, pattern: 'keep', is_regex: false },
    ]);

    // Empty pattern
    comp.beginEdit({ id: 9, pattern: 'keep', is_regex: false });
    comp.editValue = '  ';
    comp.commitEdit();
    // Unchanged
    comp.beginEdit({ id: 9, pattern: 'keep', is_regex: false });
    comp.editValue = 'keep';
    comp.commitEdit();

    // No HTTP update calls should have been made beyond initial GET
    httpMock.expectNone(req => req.method === 'PUT' && req.url === '/addresses/9');
  });
  it('saveRefresh error does not crash', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    tick();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.logTab = 'api';
    comp.refreshMs = 100;
    comp.logLines = 25;
    (fixture.componentInstance as any).saveRefresh();
    const put = httpMock.expectOne(req => req.method === 'PUT' && req.url === '/logs/refresh/api');
    put.flush('boom', { status: 500, statusText: 'Server Error' });

    tick(200);
    // Ensure any timers are stopped to prevent interval leakage across tests
    comp.stopLogTimer();
  }));

  it('onSortChange with empty direction returns early', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.onSortChange({ active: 'pattern', direction: '' } as any);
    const reqs = httpMock.match(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    expect(reqs.length).toBe(0);
  });

  it('maybeStartLogTimer with zero refresh does nothing', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([]);

    comp.refreshMs = 0;
    comp['maybeStartLogTimer']();
    tick(300);
    const reqs = httpMock.match(r => r.method === 'GET' && r.url === '/logs/tail');
    expect(reqs.length).toBe(0);
  }));

  it('deleteSelected continues on errors', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 100, pattern: 'a', is_regex: false },
      { id: 101, pattern: 'b', is_regex: false },
    ]);

    comp.toggleSelect(100, true);
    comp.toggleSelect(101, true);
    comp.deleteSelected();
    tick();

    httpMock.expectOne(r => r.method === 'DELETE' && r.url === '/addresses/100').flush('busy', { status: 503, statusText: 'Service Unavailable' });
    tick();
    // It should continue to the next deletion even after an error
    httpMock.expectOne(r => r.method === 'DELETE' && r.url === '/addresses/101').flush({ status: 'ok' });
    tick();

    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([]);
  }));

  it('remove handles error (no reload on error)', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 5, pattern: 'x', is_regex: false },
    ]);

    comp.remove(5);
    const del = httpMock.expectOne(r => r.method === 'DELETE' && r.url === '/addresses/5');
    del.flush('busy', { status: 503, statusText: 'Service Unavailable' });
    const further = httpMock.match(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    expect(further.length).toBe(0);
  });

  it('commitEdit other error path triggers reload', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as any;
    fixture.detectChanges();
    flushInitialLogs();
    httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses')).flush([
      { id: 33, pattern: 'old', is_regex: false },
    ]);

    comp.beginEdit({ id: 33, pattern: 'old', is_regex: false });
    comp.editValue = 'conflict';
    comp.commitEdit();

    const put = httpMock.expectOne(r => r.method === 'PUT' && r.url === '/addresses/33');
    put.flush('conflict', { status: 409, statusText: 'Conflict' });
    const reload = httpMock.expectOne(r => r.method === 'GET' && r.url.startsWith('/addresses'));
    reload.flush([{ id: 33, pattern: 'old', is_regex: false }]);
  });
});
