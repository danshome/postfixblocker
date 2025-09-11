import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

interface Entry { id: number; pattern: string; is_regex: boolean; }

@Component({
  selector: 'app-root',
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
    this.http.get<Entry[]>('/addresses').subscribe(data => this.entries = data);
  }

  add(): void {
    this.http.post('/addresses', { pattern: this.newPattern, is_regex: this.isRegex })
      .subscribe(() => {
        this.newPattern = '';
        this.isRegex = false;
        this.load();
      });
  }

  remove(id: number): void {
    this.http.delete(`/addresses/${id}`).subscribe(() => this.load());
  }
}
