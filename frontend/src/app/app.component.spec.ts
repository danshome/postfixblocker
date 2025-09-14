import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AppComponent } from './app.component';

interface Entry { id: number; pattern: string; is_regex: boolean; }

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      // Import standalone component and testing HttpClient
      imports: [AppComponent, HttpClientTestingModule],
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

  it('adds an entry then reloads and resets form', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Initial GET
    httpMock.expectOne('/addresses').flush([]);

    comp.newPattern = 'new@example.com';
    comp.isRegex = false;
    comp.add();

    const post = httpMock.expectOne('/addresses');
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ pattern: 'new@example.com', is_regex: false });
    post.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after add
    const reload = httpMock.expectOne('/addresses');
    expect(reload.request.method).toBe('GET');
    reload.flush([{ id: 2, pattern: 'new@example.com', is_regex: false }]);

    expect(comp.newPattern).toBe('');
    expect(comp.isRegex).toBe(false);
    expect(comp.entries.length).toBe(1);
  });

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

  it('adds bulk entries (two lines) and reloads', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance;
    fixture.detectChanges();

    // Initial GET
    httpMock.expectOne('/addresses').flush([]);

    comp.bulkText = 'a1@example.com\n a2@example.com\n';
    comp.bulkIsRegex = false;
    const promise = comp.addBulk();

    const post1 = httpMock.expectOne('/addresses');
    expect(post1.request.method).toBe('POST');
    expect(post1.request.body).toEqual({ pattern: 'a1@example.com', is_regex: false });
    post1.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Allow microtask turn for next HTTP to be enqueued
    await Promise.resolve();
    const post2 = httpMock.expectOne('/addresses');
    expect(post2.request.method).toBe('POST');
    expect(post2.request.body).toEqual({ pattern: 'a2@example.com', is_regex: false });
    post2.flush({ status: 'ok' }, { status: 201, statusText: 'Created' });

    // Reload after bulk
    await Promise.resolve();
    const reload = httpMock.expectOne('/addresses');
    expect(reload.request.method).toBe('GET');
    reload.flush([
      { id: 1, pattern: 'a1@example.com', is_regex: false },
      { id: 2, pattern: 'a2@example.com', is_regex: false },
    ]);

    await promise;
    expect(comp.bulkText).toBe('');
    expect(comp.bulkIsRegex).toBe(false);
    expect(comp.entries.length).toBe(2);
  });
});
