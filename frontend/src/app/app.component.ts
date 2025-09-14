import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

interface Entry { id: number; pattern: string; is_regex: boolean; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html'
})
export class AppComponent implements OnInit {
  entries: Entry[] = [];
  newPattern = '';
  isRegex = false;
  bulkText = '';
  bulkIsRegex = false;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.http.get<Entry[]>('/addresses').subscribe({
      next: data => (this.entries = data),
      error: () => (this.entries = []),
    });
  }

  add(): void {
    this.http
      .post('/addresses', {
        pattern: this.newPattern,
        is_regex: this.isRegex,
      })
      .subscribe({
        next: () => {
          this.newPattern = '';
          this.isRegex = false;
          this.load();
        },
        error: () => {
          // Keep form values so user can retry when backend becomes available
        },
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
      this.load();
    }
  }

  remove(id: number): void {
    this.http
      .delete(`/addresses/${id}`)
      .subscribe({ next: () => this.load(), error: () => {} });
  }
}
