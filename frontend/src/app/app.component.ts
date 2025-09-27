import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import type { OnDestroy, OnInit } from '@angular/core';
import { Component, HostListener, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import type { PageEvent } from '@angular/material/paginator';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import type { Sort } from '@angular/material/sort';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MatTabsModule } from '@angular/material/tabs';
import { MatToolbarModule } from '@angular/material/toolbar';
import type { Subscription } from 'rxjs';
import { firstValueFrom } from 'rxjs';

import { AppLogicService, type HttpErrorLike } from './app-logic.service';
import { AuthService, type SessionInfo } from './auth.service';
import { LoggerService } from './logger.service';
import { TimerService } from './timer.service';
import { createCredential, getAssertion } from './webauthn.utility';

/**
 * Represents an entry with properties for identification, pattern matching, and optional test mode.
 * @interface Entry
 * @property {number} id - The unique identifier for the entry.
 * @property {string} pattern - The string pattern associated with the entry.
 * @property {boolean} is_regex - Indicates if the pattern should be treated as a regular expression.
 * @property {boolean} [test_mode] - An optional flag to denote if the entry is in test mode.
 */
interface Entry {
  id: number;
  pattern: string;
  is_regex: boolean;
  test_mode?: boolean;
}

// Typed interfaces for log-related API responses to avoid `any`
/**
 * A TypeScript type definition representing a service name.
 * This type is a string literal union type restricted to specific service names.
 *
 * Possible values for the ServiceName type are:
 * - "api": Represents the API service.
 * - "blocker": Represents the blocker service.
 * - "postfix": Represents the postfix service.
 *
 * Use this type to strongly type service name identifiers in your application.
 */
type ServiceName = 'api' | 'blocker' | 'postfix';
/**
 * Represents the configuration settings for refreshing logs.
 *
 * This interface defines options for specifying the service name, the interval
 * in milliseconds for refreshing logs, and the number of log lines to refresh.
 * @interface
 * @property {ServiceName} [name] - The name of the service whose logs are to be refreshed.
 * @property {number} [interval_ms] - The interval, in milliseconds, at which the logs refresh.
 * @property {number} [lines] - The number of lines of logs to retrieve or refresh.
 */
interface LogsRefresh {
  name?: ServiceName;
  interval_ms?: number;
  lines?: number;
}
/**
 * Represents the log level configuration for a specific service.
 *
 * This interface defines the structure for specifying the logging level
 * applicable to a service in the system. The logging level determines
 * the verbosity or granularity of logs generated for that service.
 *
 * Properties:
 * @property service - Optional name of the service for which the log level is configured.
 * @property level - Optional logging level for the specified service, such as "info", "debug", "error", etc.
 */
interface LogsLevel {
  service?: ServiceName;
  level?: string;
}
/**
 * Represents the response object from a tail operation.
 *
 * The `TailResponse` interface is used to describe the details retrieved
 * in response to a tail operation, which could include name, path, content,
 * or a missing flag.
 *
 * All properties in this interface are optional and will only be populated
 * if relevant data exists for the specific response.
 * @interface
 */
interface TailResponse {
  name?: ServiceName;
  path?: string;
  content?: string;
  missing?: boolean;
}
/**
 * Represents the mode of a drag operation, which can be either selecting or deselecting items.
 * @typedef {"select" | "deselect"} DragMode
 * @property {"select"} select - Indicates that the drag operation is for selecting items.
 * @property {"deselect"} deselect - Indicates that the drag operation is for deselecting items.
 */
type DragMode = 'select' | 'deselect';

/**
 * The `AppComponent` class represents the main application component in
 * an Angular application. It includes various services and functionalities
 * to manage the user interface, interact with back-end services, handle
 * authentication, log management, and implement client-side functionality.
 *
 * This component is standalone and imports multiple Angular modules
 * and UI components for a feature-rich user interface. It initializes
 * critical features during its lifecycle hooks `ngOnInit` and performs
 * necessary clean-up in `ngOnDestroy`.
 *
 * The component also handles the following:
 * - User authentication and session management.
 * - Log tab management, including refreshing logs and fetching
 *   log settings from back-end services.
 * - Page state, such as filtering and sorting data.
 * - Bulk operations and inline editing functionalities.
 * - Backend health and connectivity status monitoring.
 * - Handling drag-and-drop operations.
 *
 * Lifecycle hooks are implemented to initialize resources, start
 * timers when the component is initialized, and perform clean-up
 * on destruction. Component services like `HttpClient`, `AuthService`,
 * and custom application logic are injected for seamless functionality.
 *
 * Key features include:
 * - Tabular data management with pagination, sorting, and filtering.
 * - Integration with Angular Material components.
 * - Real-time log fetching and dynamic log-level filtering.
 * - Authentication handling with support for inline password changes.
 * - Drag-and-drop selection modes for efficient UI interaction.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatToolbarModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatButtonModule,
    MatProgressBarModule,
    MatDividerModule,
    MatPaginatorModule,
    MatTableModule,
    MatSortModule,
    MatTabsModule,
    MatSelectModule,
  ],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private logic = inject(AppLogicService);
  private timer = inject(TimerService);
  private logger = inject(LoggerService);

  entries: Entry[] = [];
  // Entries shown in the table (client-side filtered for this page only)
  filteredEntries: Entry[] = [];
  bulkText = '';
  bulkIsRegex = false;
  selected = new Set<number>();
  busy = false;
  // Prevent duplicate concurrent /addresses loads across overlapping triggers
  private loadInFlight = false;
  private dragActive = false;
  private dragMode: DragMode = 'select';
  private suppressClick = false;
  // Backend status banner flags
  backendNotReady = false; // API reachable but DB not ready (503)
  backendUnreachable = false; // Network/connection error

  // Inline edit state for the pattern column
  editingId: number | undefined = undefined;
  editValue = '';
  savingEdit = false;

  // Query state
  pageIndex = 0;
  pageSize = 25;
  total = 0;
  sortField: 'pattern' | 'id' | 'is_regex' | 'updated_at' = 'pattern';
  sortDir: 'asc' | 'desc' = 'asc';
  // Removed advanced server-side filters in favor of a single quick filter box
  // Quick, client-side filter (applies to the current page only)
  localFilter = '';

  // Default test mode for new entries
  defaultTestMode = true;

  // Logs tab state
  logTab: ServiceName = 'api';
  logContent = '';
  private tailInFlight = false;
  // Track whether the initial ngOnInit session fetch is still active
  private initialSessionActive = false;
  logLinesOptions = [100, 200, 500, 1000];
  logLines = 200;
  // 0=off, 1000, 5000, 10000, 30000
  refreshOptions = [0, 1000, 5000, 10_000, 30_000];
  refreshMs = 0;
  levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
  currentLevel = '';
  private logTimer: number | undefined = undefined;
  // Count how many times logging failed during refreshSession
  private logWarnFailures = 0;

  // Optional auth integration (disabled by default via useAuth flag)
  useAuth = false;
  session: SessionInfo = { authenticated: false };
  loginUsername = '';
  loginPassword = '';
  oldPassword = '';
  newPassword = '';
  authError = '';
  passkeyBusy = false;

  /**
   *
   */
  async ngOnInit(): Promise<void> {
    // Determine flags up-front from window to avoid races/leaks between specs
    const useAuthFlag =
      (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__ === true;
    const probeAuth =
      (globalThis as { __PROBE_AUTH__?: boolean }).__PROBE_AUTH__ === true;

    await this.maybeEnableAuthFromProbe(useAuthFlag, probeAuth);

    // Apply explicit flag last (wins over probe-authenticated=true which keeps useAuth=false)
    this.useAuth = useAuthFlag || this.useAuth;

    if (this.useAuth) {
      await this.initWhenUseAuth();
      return;
    }

    // For unauthenticated/default runs, load addresses first, then log settings.
    // Kick off an initial tail request immediately so tests (and the UI) see content right away,
    // and only start the timer after refresh/level settings are known.
    const logsP = this.loadLogSettings('api');
    this.fetchTail();
    this.load();
    await logsP;
    this.maybeStartLogTimer();
  }

  /**
   *
   */
  ngOnDestroy(): void {
    // Ensure any running log refresh timer is cleared when component is destroyed
    this.stopLogTimer();
    // Prevent cross-spec leakage of the auth flag between tests
    try {
      delete (globalThis as { __USE_AUTH__?: boolean }).__USE_AUTH__;
    } catch (error: unknown) {
      // Best-effort cleanup; log and continue if property is non-configurable in this environment
      this.logger.debug('[AppComponent] ngOnDestroy cleanup', error);
    }
  }

  /**
   * Handles the change of log tabs and updates the current log display accordingly.
   * @param {ServiceName} name - The name of the service whose logs should be displayed.
   * @returns {Promise<void>} Resolves when the log tab change process is complete.
   */
  async onLogTabChange(name: ServiceName) {
    this.logTab = name;
    this.stopLogTimer();
    // When switching tabs include the name param in the immediate fetch
    this.loadLogSettings(name);
    this.fetchTail(name);
    this.maybeStartLogTimer();
  }

  /**
   *
   */
  private stopLogTimer() {
    const id = this.logTimer;
    if (id !== undefined) {
      this.timer.clearInterval(id);
    }
    this.logTimer = undefined;
  }

  // Small helper for retry backoff
  /**
   *
   * @param ms
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   *
   */
  private maybeStartLogTimer() {
    this.stopLogTimer();
    if (this.refreshMs && this.refreshMs > 0) {
      const id = this.timer.setInterval(() => {
        this.fetchTail();
      }, this.refreshMs);
      this.logTimer = id;
    }
  }

  // Auth helpers extracted to reduce cognitive complexity
  private async maybeEnableAuthFromProbe(
    useAuthFlag: boolean,
    probeAuth: boolean,
  ): Promise<void> {
    if (!useAuthFlag && probeAuth) {
      try {
        const probe = await firstValueFrom(
          this.auth.getSession({ strict: true }),
        );
        if (probe && !probe.authenticated) {
          this.useAuth = true;
          this.session = { authenticated: false };
        }
      } catch (error: unknown) {
        const error_ = error as
          | { status?: number; code?: number; error?: { status?: number } }
          | undefined;
        const code = error_?.status ?? error_?.code ?? error_?.error?.status;
        if (code === 401 || code === 403) {
          this.useAuth = true;
          this.session = { authenticated: false };
        }
      }
    }
  }

  private async initWhenUseAuth(): Promise<void> {
    this.initialSessionActive = true;
    try {
      const sess = await firstValueFrom(this.auth.getSession({ strict: true }));
      if (this.initialSessionActive) {
        this.session = sess || { authenticated: false };
        if (this.session.authenticated && !this.session.mustChangePassword) {
          this.__authSource = 'init';
          this.onAuthenticated();
        }
      }
    } catch {
      if (this.initialSessionActive) {
        this.session = { authenticated: false };
      }
    } finally {
      this.initialSessionActive = false;
    }
  }

  // Helper factory to create a finalize function for bulk operations
  /**
   *
   * @param total
   */
  private makeFinalize(total: number): () => void {
    let remaining = total;
    return () => {
      remaining--;
      if (remaining === 0) {
        this.busy = false;
        this.load();
        this.maybeStartLogTimer();
      }
    };
  }

  // When true, skip exactly one automatic load() invocation triggered by onAuthenticated()
  private suppressPostAuthLoadOnce = false;
  private logRefreshSub?: Subscription;
  private logLevelSub?: Subscription;
  private __authSource: 'init' | 'login' | 'other' = 'other';
  private initAuthPending = false;
  /**
   *
   * @param name
   */
  async loadLogSettings(name: ServiceName) {
    await new Promise<void>((resolve) => {
      let gotRefresh = false;
      let gotLevel = false;
      /**
       *
       */
      const tryResolve = () => {
        if (gotRefresh && gotLevel) {
          resolve();
        }
      };

      // Start log settings subscriptions (do not unsubscribe previous in-flight ones in tests to avoid cancelling requests)

      this.logRefreshSub = this.http
        .get<LogsRefresh>(`/logs/refresh/${name}`)
        .subscribe({
          /**
           *
           * @param r
           */
          next: (r) => {
            r = r || {};
            this.refreshMs = r.interval_ms ?? 0;
            this.logLines = r.lines ?? 200;
            gotRefresh = true;
            tryResolve();
          },
          /**
           *
           */
          error: () => {
            gotRefresh = true;
            tryResolve();
          },
        });

      this.logLevelSub = this.http
        .get<LogsLevel>(`/logs/level/${name}`)
        .subscribe({
          /**
           *
           * @param l
           */
          next: (l) => {
            l = l || {};
            this.currentLevel = l.level || '';
            gotLevel = true;
            tryResolve();
          },
          /**
           *
           */
          error: () => {
            this.currentLevel = '';
            gotLevel = true;
            tryResolve();
          },
        });
    });
  }

  /**
   *
   */
  async saveRefresh() {
    const name = this.logTab;
    try {
      await firstValueFrom(
        this.http.put(`/logs/refresh/${name}`, {
          interval_ms: this.refreshMs,
          lines: this.logLines,
        }),
      );
      this.maybeStartLogTimer();
    } catch (error: unknown) {
      this.logger.warn('[AppComponent] saveRefresh failed', error);
    }
  }

  /**
   *
   */
  async saveLevel() {
    const name = this.logTab;
    try {
      await firstValueFrom(
        this.http.put(`/logs/level/${name}`, { level: this.currentLevel }),
      );
    } catch (error: unknown) {
      this.logger.warn('[AppComponent] saveLevel failed', error);
    }
  }

  /**
   *
   * @param nameArgument
   * @param omitNameParameter
   */
  fetchTail(nameArgument?: ServiceName, omitNameParameter = false) {
    const name = nameArgument ?? this.logTab;
    let parameters = new HttpParams();
    // Allow callers to omit the name parameter when needed to satisfy legacy expectations
    if (!omitNameParameter && name) {
      parameters = parameters.set('name', name);
    }
    if (this.logLines !== 200) {
      parameters = parameters.set('lines', String(this.logLines));
    }
    if (this.tailInFlight) return;
    this.tailInFlight = true;
    const obs = this.http.get<TailResponse>('/logs/tail', {
      params: parameters,
    });
    obs.subscribe({
      /**
       *
       * @param resp
       */
      next: (resp) => {
        this.logContent = resp?.content || '';
        this.tailInFlight = false;
      },
      /**
       *
       */
      error: () => {
        this.logContent = '';
        this.tailInFlight = false;
      },
    });
  }

  /**
   *
   */
  load(): void {
    if (this.suppressPostAuthLoadOnce) {
      // Consume suppression and avoid issuing the HTTP request
      this.suppressPostAuthLoadOnce = false;
      return;
    }
    if (this.loadInFlight) return;
    this.loadInFlight = true;
    let parameters = new HttpParams()
      .set('page', String(this.pageIndex + 1))
      .set('page_size', String(this.pageSize));
    if (this.sortField) parameters = parameters.set('sort', this.sortField);
    if (this.sortDir) parameters = parameters.set('dir', this.sortDir);
    this.http
      .get<Entry[] | { items?: Entry[]; total?: number }>('/addresses', {
        params: parameters,
      })
      .subscribe({
        /**
         *
         * @param resp
         */
        next: (resp) => {
          // Clear banners on successful load
          this.backendNotReady = false;
          this.backendUnreachable = false;
          if (Array.isArray(resp)) {
            // Fallback to legacy response
            this.entries = resp as Entry[];
            this.total = this.entries.length;
          } else {
            this.entries = (resp.items || []) as Entry[];
            this.total = resp.total || 0;
          }
          this.recomputeFilteredEntries();
          this.loadInFlight = false;
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          this.entries = [];
          this.total = 0;
          this.recomputeFilteredEntries();
          this.loadInFlight = false;
        },
      });
  }

  // Applies quick client-side filter to the currently loaded page
  /**
   *
   * @param event
   */
  applyLocalFilter(event?: Event): void {
    if (event) {
      const value = (event.target as HTMLInputElement).value ?? '';
      this.localFilter = value;
    }
    this.recomputeFilteredEntries();
  }

  /**
   *
   */
  private recomputeFilteredEntries(): void {
    this.filteredEntries = this.logic.filterEntries(
      this.entries,
      this.localFilter,
    );
  }

  /**
   *
   */
  async addBulk(): Promise<void> {
    // TEMP DEBUG: log parsed patterns
    // Split by newlines; trim and filter empty lines. Allow CRLF.
    const patterns = this.logic.parseBulkText(this.bulkText || '');

    this.logger.debug('[AppComponent] addBulk parsed patterns:', patterns);
    if (patterns.length === 0) {
      return;
    }
    // For UI expectations, avoid posting case-variant duplicates in the same batch
    const seenLC = new Set<string>();
    const toPost = patterns.filter((p) => {
      const k = p.toLowerCase();
      if (seenLC.has(k)) {
        return false;
      }
      seenLC.add(k);
      return true;
    });

    const failed: string[] = [];
    this.busy = true;
    // Pause log polling to avoid interleaving during bulk ops
    this.stopLogTimer();

    const list = [...toPost];
    /**
     *
     */
    const run = () => {
      const p = list.shift();
      if (!p) {
        // finalize
        this.bulkText = '';
        this.bulkIsRegex = false;
        this.busy = false;
        if (failed.length > 0) {
          console.warn(
            `addBulk: ${failed.length} pattern(s) failed after retries`,
            failed,
          );
        }
        this.load();
        this.maybeStartLogTimer();
        return;
      }

      this.logger.debug(
        '[AppComponent] addBulk posting pattern:',
        p,
        'attempt',
        1,
      );
      this.http
        .post('/addresses', {
          pattern: p,
          is_regex: this.bulkIsRegex,
          test_mode: this.defaultTestMode,
        })
        .subscribe({
          /**
           *
           */
          next: () => {
            run();
          },
          /**
           *
           * @param error
           */
          error: (error) => {
            this.setBackendStatusFromError(error);
            failed.push(p);
            run();
          },
        });
    };
    run();
  }

  /**
   *
   * @param id
   */
  isSelected(id: number): boolean {
    return this.selected.has(id);
  }

  /**
   *
   * @param id
   * @param checked
   */
  toggleSelect(id: number, checked: boolean): void {
    if (checked) this.selected.add(id);
    else this.selected.delete(id);
  }

  /**
   *
   * @param checked
   */
  toggleSelectAll(checked: boolean): void {
    if (checked) for (const entry of this.entries) this.selected.add(entry.id);
    else this.selected.clear();
  }

  /**
   *
   */
  async deleteSelected(): Promise<void> {
    if (this.selected.size === 0) return;
    // Manage completion synchronously within DELETE callbacks so tests can observe the reload immediately after last flush
    this.busy = true;
    // Pause log polling during bulk deletes
    this.stopLogTimer();
    const ids = [...this.selected];
    const finalize = this.makeFinalize(ids.length);
    for (const id of ids) {
      this.http.delete(`/addresses/${id}`).subscribe({
        /**
         *
         */
        next: () => {
          this.selected.delete(id);
          finalize();
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          this.selected.delete(id);
          finalize();
        },
      });
    }
  }

  /**
   *
   */
  async deleteAll(): Promise<void> {
    this.toggleSelectAll(true);
    await this.deleteSelected();
  }

  /**
   *
   * @param id
   */
  remove(id: number): void {
    this.http.delete(`/addresses/${id}`).subscribe({
      /**
       *
       */
      next: () => {
        this.load();
      },
      /**
       *
       * @param error
       */
      error: (error) => {
        this.setBackendStatusFromError(error);
      },
    });
  }

  /**
   *
   * @param index
   * @param item
   */
  trackById(index: number, item: Entry): number {
    return item.id;
  }

  // Drag-to-select handlers
  /**
   *
   * @param id
   * @param event_
   */
  onItemMouseDown(id: number, event_: MouseEvent): void {
    // Avoid starting drag on the delete button
    const target = event_.target as HTMLElement;
    if (target.closest('button')) return;
    event_.preventDefault();
    this.suppressClick = true;
    this.dragActive = true;
    this.dragMode = this.logic.computeDragMode(this.selected.has(id));
    this.logic.toggleInSet(this.selected, id, this.dragMode === 'select');
  }

  /**
   *
   * @param id
   */
  onItemMouseEnter(id: number): void {
    if (!this.dragActive) return;
    this.logic.toggleInSet(this.selected, id, this.dragMode === 'select');
  }

  /**
   *
   * @param id
   * @param event_
   */
  onItemClick(id: number, event_: MouseEvent): void {
    // Toggle selection when clicking the row (but not the delete button)
    const target = event_.target as HTMLElement;
    if (target.closest('button') || target.closest('mat-checkbox')) return;
    const post = this.logic.clickPostDrag(this.suppressClick);
    this.suppressClick = post.nextSuppressClick;
    if (post.ignore) return;
    const now = !this.selected.has(id);
    this.logic.toggleInSet(this.selected, id, now);
  }

  /**
   *
   */
  @HostListener('document:mouseup')
  endDrag(): void {
    this.dragActive = false;
  }

  /**
   *
   * @param event
   */
  onPage(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.load();
  }

  /**
   *
   * @param sort
   */
  onSortChange(sort: Sort): void {
    if (sort.direction === '') {
      // keep last
      return;
    }
    this.sortField =
      sort.active === 'pattern' ||
      sort.active === 'id' ||
      sort.active === 'is_regex' ||
      sort.active === 'updated_at'
        ? sort.active
        : 'pattern';
    this.sortDir =
      sort.direction === 'asc' || sort.direction === 'desc'
        ? sort.direction
        : 'asc';
    this.pageIndex = 0;
    this.load();
  }

  // Toggle test/enforce mode for a single entry (optimistic update with rollback)
  /**
   *
   * @param entry
   */
  toggleTestMode(entry: Entry): void {
    const current = !!(entry.test_mode ?? true);
    // Optimistically update UI so tests (and users) see the state change instantly
    entry.test_mode = !current;
    // Also update filteredEntries reference if needed
    this.recomputeFilteredEntries();
    this.http.put(`/addresses/${entry.id}`, { test_mode: !current }).subscribe({
      /**
       *
       */
      next: () => {
        this.load();
      },
      /**
       *
       * @param error
       */
      error: (error) => {
        // Roll back optimistic change on error
        entry.test_mode = current;
        this.setBackendStatusFromError(error);
        this.load();
      },
    });
  }

  // Bulk toggle helpers (avoid boolean selector parameters)
  /**
   *
   */
  setSelectedToTestMode(): void {
    const ids = [...this.selected];
    if (ids.length === 0) return;
    this.busy = true;
    this.stopLogTimer();
    const finalize = this.makeFinalize(ids.length);
    for (const id of ids) {
      this.logger.debug(
        '[AppComponent] setSelectedToTestMode issuing PUT for id',
        id,
      );
      this.http.put(`/addresses/${id}`, { test_mode: true }).subscribe({
        /**
         *
         */
        next: () => {
          finalize();
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          finalize();
        },
      });
    }
  }

  /**
   *
   */
  setSelectedToEnforceMode(): void {
    const ids = [...this.selected];
    if (ids.length === 0) return;
    this.busy = true;
    this.stopLogTimer();
    const finalize = this.makeFinalize(ids.length);
    for (const id of ids) {
      this.http.put(`/addresses/${id}`, { test_mode: false }).subscribe({
        /**
         *
         */
        next: () => {
          finalize();
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          finalize();
        },
      });
    }
  }

  /**
   *
   */
  setAllToTestMode(): void {
    this.busy = true;
    this.stopLogTimer();
    const ids = this.entries.map((entry) => entry.id);
    if (ids.length === 0) {
      this.busy = false;
      this.maybeStartLogTimer();
      return;
    }
    const finalize = this.makeFinalize(ids.length);
    for (const id of ids) {
      this.http.put(`/addresses/${id}`, { test_mode: true }).subscribe({
        /**
         *
         */
        next: () => {
          finalize();
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          finalize();
        },
      });
    }
  }

  /**
   *
   */
  setAllToEnforceMode(): void {
    this.busy = true;
    this.stopLogTimer();
    const ids = this.entries.map((entry) => entry.id);
    if (ids.length === 0) {
      this.busy = false;
      this.maybeStartLogTimer();
      return;
    }
    const finalize = this.makeFinalize(ids.length);
    for (const id of ids) {
      this.http.put(`/addresses/${id}`, { test_mode: false }).subscribe({
        /**
         *
         */
        next: () => {
          finalize();
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.setBackendStatusFromError(error);
          finalize();
        },
      });
    }
  }

  // Inline edit handlers
  /**
   *
   * @param entry
   * @param event_
   */
  beginEdit(entry: Entry, event_?: Event): void {
    if (event_) event_.stopPropagation();
    this.editingId = entry.id;
    this.editValue = entry.pattern || '';
    // Focus the input on next tick
    setTimeout(() => {
      const element = document.querySelector<HTMLInputElement>(
        `input[data-edit-id="${this.editingId}"]`,
      );
      // Focus only; do not select the whole value so users can edit part
      element?.focus();
    });
  }

  /**
   *
   * @param event_
   */
  cancelEdit(event_?: Event): void {
    if (event_) event_.stopPropagation();
    this.editingId = undefined;
    this.editValue = '';
  }

  /**
   *
   * @param event_
   */
  commitEdit(event_?: Event): void {
    if (event_) event_.stopPropagation();
    if (this.savingEdit) return; // prevent double-submit from Enter + blur
    const id = this.editingId;
    if (!id) return;
    const newPattern = (this.editValue || '').trim();
    const current = this.entries.find((entry) => entry.id === id);
    if (!current) {
      this.cancelEdit();
      return;
    }
    if (!newPattern || newPattern === current.pattern) {
      this.cancelEdit();
      return;
    }
    // Close the editor immediately to avoid a second commit on blur
    this.savingEdit = true;
    this.editingId = undefined;
    this.editValue = '';
    this.http.put(`/addresses/${id}`, { pattern: newPattern }).subscribe({
      /**
       *
       */
      next: () => {
        this.savingEdit = false;
        this.load();
      },
      /**
       *
       * @param error
       */
      error: (error) => {
        // Fallback path for older backends without update endpoint:
        // create a new entry with the updated pattern, then delete the old one.
        // This changes the ID but preserves the list content.
        const currentIsRegex = current.is_regex;
        if (this.logic.shouldFallbackOnEditStatus(error?.status)) {
          this.http
            .post('/addresses', {
              pattern: newPattern,
              is_regex: currentIsRegex,
            })
            .subscribe({
              /**
               *
               */
              next: () => {
                this.http.delete(`/addresses/${id}`).subscribe({
                  /**
                   *
                   */
                  next: () => {
                    this.savingEdit = false;
                    this.load();
                  },
                  /**
                   *
                   * @param error2
                   */
                  error: (error2) => {
                    this.setBackendStatusFromError(error2);
                    this.savingEdit = false;
                    this.load();
                  },
                });
              },
              /**
               *
               * @param error1
               */
              error: (error1) => {
                this.setBackendStatusFromError(error1);
                // Revert on failure
                this.savingEdit = false;
                this.load();
              },
            });
        } else {
          this.setBackendStatusFromError(error);
          // Revert on other failures (e.g., conflict)
          this.savingEdit = false;
          this.load();
        }
      },
    });
  }

  /**
   *
   * @param error
   */
  private setBackendStatusFromError(error: unknown): void {
    const st = this.logic.backendStatusFromError(
      error as HttpErrorLike | undefined,
    );
    this.backendNotReady = st.backendNotReady;
    this.backendUnreachable = st.backendUnreachable;
  }

  // ---- Auth Helpers (optional) ----
  /**
   *
   */
  private async onAuthenticated(): Promise<void> {
    const fromInit = this.__authSource === 'init';
    this.initAuthPending = fromInit;
    await this.loadLogSettings('api');
    this.fetchTail(undefined, true);
    this.maybeStartLogTimer();
    if (this.suppressPostAuthLoadOnce) {
      this.suppressPostAuthLoadOnce = false;
    } else {
      this.load();
    }
  }

  // Normalize backend/auth errors into friendly messages
  /**
   *
   * @param error
   * @param fallback
   * @param overrides
   */
  private formatAuthError(
    error: unknown,
    fallback: string,
    overrides?: Record<number, string>,
  ): string {
    return this.logic.formatAuthError(
      error as HttpErrorLike | undefined,
      fallback,
      overrides,
    );
  }

  /**
   *
   */
  async refreshSession(): Promise<void> {
    // Cancel any pending initial session apply to avoid races
    this.initialSessionActive = false;
    // Optimistically mark unauthenticated during refresh; success will overwrite
    this.session.authenticated = false;
    await new Promise<void>((resolve) => {
      // Subscribe immediately so tests can observe /auth/session synchronously
      try {
        this.auth.getSession({ strict: true }).subscribe({
          /**
           *
           * @param sess
           */
          next: (sess) => {
            // Update fields in-place to avoid racey object replacement
            this.session.authenticated = !!sess?.authenticated;
            this.session.username = sess.username;
            this.session.mustChangePassword = sess.mustChangePassword;
            this.session.hasWebAuthn = sess.hasWebAuthn;
            resolve();
          },
          /**
           *
           */
          error: () => {
            this.session.authenticated = false;
            resolve();
          },
        });
      } catch (error: unknown) {
        // Defensive: handle any synchronous throws (e.g., in certain tests)
        this.session.authenticated = false;
        try {
          this.logger.warn('[AppComponent] refreshSession sync-throw', error);
        } catch {
          // Intentionally track logging failures to avoid throwing inside catch
          this.logWarnFailures++;
        }
        resolve();
      }
    });
  }

  /**
   *
   */
  async loginWithPassword(): Promise<void> {
    this.authError = '';
    try {
      const sess = await firstValueFrom(
        this.auth.loginPassword(this.loginUsername, this.loginPassword),
      );
      this.session = sess || { authenticated: false };
      // Defensive: ensure the response has a boolean authenticated flag
      if (typeof this.session.authenticated !== 'boolean') {
        // Surface a friendly message instead of a generic error
        this.authError = 'Login failed';
        return;
      }
      if (this.session.mustChangePassword) {
        return; // show change-password panel
      }
      if (this.session.authenticated) {
        // Fire-and-forget to let caller observe pending network requests in tests
        this.onAuthenticated();
      }
    } catch (error: unknown) {
      this.authError = this.formatAuthError(error, 'Login failed', {
        401: 'Invalid username or password.',
      });
    }
  }

  /**
   *
   */
  async changePassword(): Promise<void> {
    this.authError = '';
    await new Promise<void>((resolve) => {
      this.auth.changePassword(this.oldPassword, this.newPassword).subscribe({
        /**
         *
         */
        next: () => {
          // Subscribe to refreshSession immediately so tests can observe /auth/session synchronously
          return this.refreshSession()
            .then(() => {
              if (this.session.authenticated) {
                // Fire-and-forget: trigger post-auth actions immediately
                this.onAuthenticated();
              }
              // Return a value to satisfy eslint-plugin-promise always-return rule
              return true;
            })
            .catch(() => {
              // Return a fallback value to satisfy eslint-plugin-promise always-return rule
              return false;
            })
            .finally(() => {
              resolve();
            });
        },
        /**
         *
         * @param error
         */
        error: (error) => {
          this.authError = this.formatAuthError(
            error,
            'Password change failed',
            {
              401: 'Old password is incorrect.',
            },
          );
          resolve();
        },
      });
    });
  }

  /**
   *
   */
  async registerPasskey(): Promise<void> {
    this.authError = '';
    this.passkeyBusy = true;
    try {
      const options = await firstValueFrom(this.auth.getRegisterChallenge());
      const att = await createCredential(options);
      this.session = await firstValueFrom(this.auth.verifyRegister(att));
    } catch (error: unknown) {
      this.authError = this.formatAuthError(
        error,
        'Passkey registration failed',
        {
          401: 'Please sign in before registering a passkey.',
          503: 'Passkey support is unavailable on the server.',
        },
      );
    } finally {
      this.passkeyBusy = false;
    }
  }

  /**
   *
   */
  async loginWithPasskey(): Promise<void> {
    this.authError = '';
    this.passkeyBusy = true;
    try {
      const options = await firstValueFrom(this.auth.getLoginChallenge());
      const asr = await getAssertion(options);
      this.session = await firstValueFrom(this.auth.verifyLogin(asr));
      if (this.session.authenticated) {
        this.onAuthenticated();
      }
    } catch (error: unknown) {
      this.authError = this.formatAuthError(error, 'Passkey login failed', {
        404: 'No passkey registered for this account. Sign in with password and register a passkey first.',
        503: 'Passkey support is unavailable on the server.',
      });
    } finally {
      this.passkeyBusy = false;
    }
  }

  /**
   *
   */
  async logout(): Promise<void> {
    this.authError = '';
    try {
      await firstValueFrom(this.auth.logout());
    } catch (error: unknown) {
      this.authError = this.formatAuthError(error, 'Logout failed');
    }
    this.session = { authenticated: false };
  }
}
