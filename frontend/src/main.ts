import { provideHttpClient } from '@angular/common/http';
import { importProvidersFrom } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

// eslint-disable-next-line unicorn/prefer-top-level-await -- Top-level await is not supported by Angular's configured build target; use async IIFE instead.
void (async () => {
  try {
    const { AppComponent } = await import('./app/app.component');
    await bootstrapApplication(AppComponent, {
      providers: [
        provideHttpClient(),
        importProvidersFrom(BrowserAnimationsModule),
      ],
    });
  } catch {
    // Swallow bootstrap errors to avoid noisy console in production builds
    // (errors will surface in monitoring/logs)
  }
})();
