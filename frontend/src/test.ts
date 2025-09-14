import 'zone.js/testing';
import { getTestBed } from '@angular/core/testing';
import {
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting,
} from '@angular/platform-browser-dynamic/testing';

// Initialize the Angular testing environment.
getTestBed().initTestEnvironment(
  BrowserDynamicTestingModule,
platformBrowserDynamicTesting(),
);

// Prevent Karma from reporting a full page reload if something triggers beforeunload
// during the test lifecycle (e.g., devserver or plugin quirks).
(window as any).onbeforeunload = null;
