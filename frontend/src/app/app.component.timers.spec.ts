import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';
import { TimerService } from './timer.service';

/**
 * Test double for TimerService that tracks created and cleared intervals.
 */
interface IntervalRecord {
  handler: () => void;
  timeout: number;
  type: 'interval';
}
class FakeTimerService extends TimerService {
  tracked = new Set<IntervalRecord>();
  /**
   * Record an interval creation in the tracking set for assertions.
   * @param {() => void} handler - Callback to invoke on each interval tick.
   * @param {number} timeout - Interval duration in milliseconds.
   * @returns {IntervalRecord} Opaque interval identifier used for clearing.
   */
  override setInterval(handler: () => void, timeout: number): IntervalRecord {
    const id: IntervalRecord = { handler, timeout, type: 'interval' };
    this.tracked.add(id);
    return id;
  }
  /**
   * Remove an interval from the tracking set.
   * @param {IntervalRecord} id - Opaque interval identifier to clear.
   * @returns {void} Nothing.
   */
  override clearInterval(id: IntervalRecord): void {
    this.tracked.delete(id);
  }
}

/**
 * Drain initial API log requests (refresh/level/tail) and the first addresses load.
 * @param {HttpTestingController} httpMock - Angular HTTP testing controller used to match and flush requests.
 */
function drainInit(httpMock: HttpTestingController) {
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
  const g = httpMock.expectOne(
    (r) => r.method === 'GET' && r.url.startsWith('/addresses'),
  );
  g.flush([]);
}

/**
 * Drain and flush all pending HTTP requests to ensure tests do not leak between cases.
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

describe('AppComponent timers and interval cleanup', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        { provide: TimerService, useClass: FakeTimerService },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    drainAll(httpMock);
    httpMock.verify();
    expect().nothing();
  });

  it('maybeStartLogTimer creates interval and stopLogTimer clears it and test tracking set', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const comp = fixture.componentInstance as unknown as {
      refreshMs: number;
      maybeStartLogTimer: () => void;
      stopLogTimer: () => void;
      logTimer?: unknown;
    };
    fixture.detectChanges();

    drainInit(httpMock);

    // Start timer
    comp.refreshMs = 50;
    comp.maybeStartLogTimer();

    const fake = TestBed.inject(TimerService) as unknown as FakeTimerService;
    const tid = comp.logTimer;
    expect(tid).toBeTruthy();
    expect(fake.tracked.has(tid)).toBeTrue();

    // Stop timer clears both interval and tracking set
    comp.stopLogTimer();
    expect(comp.logTimer).toBeNull();
    expect(fake.tracked.has(tid)).toBeFalse();
  });
});
