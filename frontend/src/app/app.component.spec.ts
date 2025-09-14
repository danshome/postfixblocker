import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AppComponent } from './app.component';

interface Entry { id: number; pattern: string; is_regex: boolean; }

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      // Import standalone component and testing HttpClient
      imports: [AppComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads entries on init', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges(); // triggers ngOnInit -> load()

    const req = httpMock.expectOne('/addresses');
    expect(req.request.method).toBe('GET');
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

    // Initial GET
    httpMock.expectOne('/addresses').flush([]);

    comp.bulkText = 'new@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post = httpMock.expectOne(req => req.method === 'POST' && req.url === '/addresses');
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ pattern: 'new@example.com', is_regex: false });
    post.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after add
    tick();
    const reload = httpMock.expectOne(req => req.method === 'GET' && req.url === '/addresses');
    expect(reload.request.method).toBe('GET');
    reload.flush([{ id: 2, pattern: 'new@example.com', is_regex: false }]);

    expect(comp.bulkText).toBe('');
    expect(comp.bulkIsRegex).toBe(false);
    expect(comp.entries.length).toBe(1);
  }));

  it('removes an entry then reloads', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Initial GET
    httpMock.expectOne('/addresses').flush([{ id: 5, pattern: 'x@y.com', is_regex: false }]);

    comp.remove(5);
    const del = httpMock.expectOne('/addresses/5');
    expect(del.request.method).toBe('DELETE');
    del.flush({ status: 'deleted' });

    // Reload after delete
    const reload = httpMock.expectOne('/addresses');
    expect(reload.request.method).toBe('GET');
    reload.flush([]);
    expect(comp.entries.length).toBe(0);
  });

  it('adds multiple entries from paste box (two lines) and reloads', fakeAsync(() => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Initial GET
    httpMock.expectOne('/addresses').flush([]);

    comp.bulkText = 'a1@example.com\n a2@example.com\n';
    comp.bulkIsRegex = false;
    comp.addBulk();
    tick();

    const post1 = httpMock.expectOne(req => req.method === 'POST' && req.url === '/addresses');
    expect(post1.request.method).toBe('POST');
    expect(post1.request.body).toEqual({ pattern: 'a1@example.com', is_regex: false });
    post1.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    tick();
    const post2 = httpMock.expectOne(req => req.method === 'POST' && req.url === '/addresses');
    expect(post2.request.method).toBe('POST');
    expect(post2.request.body).toEqual({ pattern: 'a2@example.com', is_regex: false });
    post2.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after bulk
    tick();
    const reload = httpMock.expectOne(req => req.method === 'GET' && req.url === '/addresses');
    expect(reload.request.method).toBe('GET');
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

    // Initial GET with two entries
    httpMock.expectOne('/addresses').flush([
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
    const reload = httpMock.expectOne('/addresses');
    reload.flush([]);

    expect(comp.selected.size).toBe(0);
  }));
});
