import 'zone.js/testing';
import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';

// Initialize the Angular testing environment using non-deprecated testing providers.
getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());

// Prevent Karma from reporting a full page reload if something triggers beforeunload
// during the test lifecycle (e.g., devserver or plugin quirks).
(window as any).onbeforeunload = null;
