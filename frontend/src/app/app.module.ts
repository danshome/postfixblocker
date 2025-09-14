// Legacy NgModule kept for reference. Not used in standalone bootstrap.
import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { AppComponent } from './app.component';

@NgModule({
  declarations: [],
  imports: [BrowserModule, HttpClientModule, FormsModule, AppComponent],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule {}
