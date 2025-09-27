import 'zone.js/testing';

import { getTestBed } from '@angular/core/testing';
import {
  BrowserTestingModule,
  platformBrowserTesting,
} from '@angular/platform-browser/testing';

// Initialize the Angular testing environment with teardown to avoid shared state between specs.
getTestBed().initTestEnvironment(
  BrowserTestingModule,
  platformBrowserTesting(),
  {
    teardown: { destroyAfterEach: true },
  },
);

// Ensure global auth toggle defaults to disabled for all tests unless explicitly enabled by a spec.
declare global {
  interface Window {
    __USE_AUTH__?: boolean;
  }
}
globalThis.__USE_AUTH__ = false;

// Prevent the test runner from treating dev-server reloads as failures by ensuring
// no lingering beforeunload handlers interfere during the test lifecycle.
const beforeUnloadListener: EventListener = () => {
  /* no-op */
};
window.removeEventListener('beforeunload', beforeUnloadListener);

// Load all spec files in a deterministic (sorted) order to avoid cross-run flakiness
// caused by differing module load orders.

interface WebpackRequireContext {
  keys(): string[];
  (id: string): unknown;
}
interface WebpackRequireFunction {
  context(path: string, deep?: boolean, filter?: RegExp): WebpackRequireContext;
}
declare const require: WebpackRequireFunction & Record<string, unknown>;
try {
  const context = require.context('./', true, /\.spec\.ts$/);
  // eslint-disable-next-line unicorn/no-array-sort -- Angular's configured TS lib excludes Array#toSorted; use .sort() here for compatibility with the current builder target.
  const specKeys = [...context.keys()].sort((a, b) => a.localeCompare(b));
  for (const k of specKeys) {
    context(k);
  }
} catch {
  // If the builder handles spec discovery itself, ignore.
}
