import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

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

  remove(id: number): void {
    this.http
      .delete(`/addresses/${id}`)
      .subscribe({ next: () => this.load(), error: () => {} });
  }
}
