import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatButtonModule } from '@angular/material/button';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatDividerModule } from '@angular/material/divider';
import { HostListener } from '@angular/core';

interface Entry { id: number; pattern: string; is_regex: boolean; }

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
    MatListModule,
    MatIconModule,
    MatProgressBarModule,
    MatDividerModule,
    MatPaginatorModule,
    MatTableModule,
    MatSortModule,
  ],
  templateUrl: './app.component.html'
})
export class AppComponent implements OnInit {
  entries: Entry[] = [];
  // Entries shown in the table (client-side filtered for this page only)
  filteredEntries: Entry[] = [];
  bulkText = '';
  bulkIsRegex = false;
  selected = new Set<number>();
  busy = false;
  private dragActive = false;
  private dragMode: 'select' | 'deselect' = 'select';
  private suppressClick = false;

  // Inline edit state for the pattern column
  editingId: number | null = null;
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

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const params: any = {
      page: this.pageIndex + 1,
      page_size: this.pageSize,
      sort: this.sortField,
      dir: this.sortDir,
    };
    this.http.get<any>('/addresses', { params }).subscribe({
      next: resp => {
        if (Array.isArray(resp)) {
          // Fallback to legacy response
          this.entries = resp as Entry[];
          this.total = this.entries.length;
        } else {
          this.entries = (resp.items || []) as Entry[];
          this.total = resp.total || 0;
        }
        this.recomputeFilteredEntries();
      },
      error: () => {
        this.entries = [];
        this.total = 0;
        this.recomputeFilteredEntries();
      },
    });
  }

  // Applies quick client-side filter to the currently loaded page
  applyLocalFilter(event?: Event): void {
    if (event) {
      const value = (event.target as HTMLInputElement).value ?? '';
      this.localFilter = value;
    }
    this.recomputeFilteredEntries();
  }

  private recomputeFilteredEntries(): void {
    const q = (this.localFilter || '').trim().toLowerCase();
    if (!q) {
      this.filteredEntries = this.entries.slice();
      return;
    }
    this.filteredEntries = this.entries.filter(e => {
      const id = String(e.id);
      const pattern = (e.pattern || '').toLowerCase();
      const isRegex = e.is_regex ? 'yes' : 'no';
      return id.includes(q) || pattern.includes(q) || isRegex.includes(q);
    });
  }

  async addBulk(): Promise<void> {
    // Split by newlines; trim and filter empty lines. Allow CRLF.
    const raw = this.bulkText || '';
    const lines = raw
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(s => s.length > 0);
    if (lines.length === 0) {
      return;
    }
    // Deduplicate while preserving order
    const seen = new Set<string>();
    const patterns: string[] = [];
    for (const s of lines) {
      if (!seen.has(s)) {
        seen.add(s);
        patterns.push(s);
      }
    }
    try {
      this.busy = true;
      for (const p of patterns) {
        try {
          await firstValueFrom(
            this.http.post('/addresses', { pattern: p, is_regex: this.bulkIsRegex })
          );
        } catch {
          // ignore individual failures and continue
        }
      }
    } finally {
      this.bulkText = '';
      this.bulkIsRegex = false;
      this.busy = false;
      this.load();
    }
  }

  isSelected(id: number): boolean {
    return this.selected.has(id);
  }

  toggleSelect(id: number, checked: boolean): void {
    if (checked) this.selected.add(id);
    else this.selected.delete(id);
  }

  toggleSelectAll(checked: boolean): void {
    if (checked) this.entries.forEach(e => this.selected.add(e.id));
    else this.selected.clear();
  }

  async deleteSelected(): Promise<void> {
    if (this.selected.size === 0) return;
    try {
      this.busy = true;
      for (const id of Array.from(this.selected)) {
        try {
          await firstValueFrom(this.http.delete(`/addresses/${id}`));
          this.selected.delete(id);
        } catch {
          // Continue even if a deletion fails
        }
      }
    } finally {
      this.busy = false;
      this.load();
    }
  }

  async deleteAll(): Promise<void> {
    this.toggleSelectAll(true);
    await this.deleteSelected();
  }

  remove(id: number): void {
    this.http
      .delete(`/addresses/${id}`)
      .subscribe({ next: () => this.load(), error: () => {} });
  }

  trackById(index: number, item: Entry): number {
    return item.id;
  }

  // Drag-to-select handlers
  onItemMouseDown(id: number, ev: MouseEvent): void {
    // Avoid starting drag on the delete button
    const target = ev.target as HTMLElement;
    if (target.closest('button')) return;
    ev.preventDefault();
    this.suppressClick = true;
    this.dragActive = true;
    this.dragMode = this.selected.has(id) ? 'deselect' : 'select';
    this.toggleSelect(id, this.dragMode === 'select');
  }

  onItemMouseEnter(id: number): void {
    if (!this.dragActive) return;
    this.toggleSelect(id, this.dragMode === 'select');
  }

  onItemClick(id: number, ev: MouseEvent): void {
    // Toggle selection when clicking the row (but not the delete button)
    const target = ev.target as HTMLElement;
    if (target.closest('button') || target.closest('mat-checkbox')) return;
    if (this.suppressClick) {
      // Click immediately following mousedown selection; ignore to avoid double-toggle
      this.suppressClick = false;
      return;
    }
    const now = !this.selected.has(id);
    this.toggleSelect(id, now);
  }

  @HostListener('document:mouseup')
  endDrag(): void {
    this.dragActive = false;
  }

  onPage(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.load();
  }

  onSortChange(sort: Sort): void {
    if (sort.direction === '') {
      // keep last
      return;
    }
    this.sortField = (sort.active as any) || 'pattern';
    this.sortDir = (sort.direction as any) || 'asc';
    this.pageIndex = 0;
    this.load();
  }

  // Inline edit handlers
  beginEdit(entry: Entry, ev?: Event): void {
    if (ev) ev.stopPropagation();
    this.editingId = entry.id;
    this.editValue = entry.pattern || '';
    // Focus the input on next tick
    setTimeout(() => {
      const el = document.querySelector(
        `input[data-edit-id="${this.editingId}"]`
      ) as HTMLInputElement | null;
      // Focus only; do not select the whole value so users can edit part
      el?.focus();
    });
  }

  cancelEdit(ev?: Event): void {
    if (ev) ev.stopPropagation();
    this.editingId = null;
    this.editValue = '';
  }

  commitEdit(ev?: Event): void {
    if (ev) ev.stopPropagation();
    if (this.savingEdit) return; // prevent double-submit from Enter + blur
    const id = this.editingId;
    if (!id) return;
    const newPattern = (this.editValue || '').trim();
    const current = this.entries.find(e => e.id === id);
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
    this.editingId = null;
    this.editValue = '';
    this.http
      .put(`/addresses/${id}`, { pattern: newPattern })
      .subscribe({
        next: () => {
          this.savingEdit = false;
          this.load();
        },
        error: (err) => {
          // Fallback path for older backends without update endpoint:
          // create a new entry with the updated pattern, then delete the old one.
          // This changes the ID but preserves the list content.
          const currentIsRegex = current.is_regex;
          if (err && (err.status === 404 || err.status === 405 || err.status === 501)) {
            this.http
              .post('/addresses', { pattern: newPattern, is_regex: currentIsRegex })
              .subscribe({
                next: () => {
                  this.http.delete(`/addresses/${id}`).subscribe({
                    next: () => {
                      this.savingEdit = false;
                      this.load();
                    },
                    error: () => {
                      this.savingEdit = false;
                      this.load();
                    },
                  });
                },
                error: () => {
                  // Revert on failure
                  this.savingEdit = false;
                  this.load();
                },
              });
          } else {
            // Revert on other failures (e.g., conflict)
            this.savingEdit = false;
            this.load();
          }
        },
      });
  }
}
