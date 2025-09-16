import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AppComponent } from './app.component';

interface Entry { id: number; pattern: string; is_regex: boolean; }

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
});
