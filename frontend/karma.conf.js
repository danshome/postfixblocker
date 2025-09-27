// Karma configuration for Angular 20 + Jasmine
module.exports = function (config) {
  // Prefer Playwright Chromium if available to ensure headless runs without a system Chrome
  try {
    const p = require('playwright-core').chromium.executablePath();
    // Only use Playwright binary if it actually exists on disk; otherwise let Karma pick system Chrome
    if (require('fs').existsSync(p)) {
      process.env.CHROME_BIN = p;
    }
  } catch (e) {
      console.warn('Failed to get Playwright Chrome binary, falling back to system Chrome:', e);
  }

  const isCI = !!(process.env.CI || process.env.GITHUB_ACTIONS || process.env.CHROME_NO_SANDBOX);

  // Coverage thresholds are disabled by default for local/test runs; override via env if needed
  const FE_MIN = parseInt(process.env.FE_COV_MIN || process.env.COVERAGE_MIN_FE || '85', 10) || 0;
  const FE_BRANCH_MIN = parseInt(process.env.FE_BRANCH_MIN || process.env.COVERAGE_MIN_FE_BRANCH || '85', 10) || 0;

  const customLaunchers = {
    ChromeHeadlessNoSandbox: {
      base: 'ChromeHeadless',
      flags: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--disable-software-rasterizer',
      ],
    },
  };

  config.set({
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    // Enforce that every spec has at least one expectation
    jasmine: {
      failSpecWithNoExpectations: true,
      // Make test ordering deterministic across runs to avoid order-dependent flakes
      random: false,
    },
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('karma-jasmine-html-reporter'),
      require('karma-coverage'),
      require('@angular-devkit/build-angular/plugins/karma'),
    ],
    client: {
      clearContext: true,
      jasmine: {
        random: false,
      },
    },
    reporters: ['progress', 'kjhtml', 'coverage'],
    coverageReporter: {
      dir: require('path').join(__dirname, './coverage'),
      subdir: '.',
      reporters: [
        { type: 'html' },
        { type: 'text-summary' },
        // Provide LCOV output for CI artifact uploads
        { type: 'lcovonly', file: 'coverage.lcov' },
      ],
      check: {
        global: {
          statements: FE_MIN,
          lines: FE_MIN,
          functions: FE_MIN,
          branches: FE_BRANCH_MIN,
        },
      },
    },
    customLaunchers,
    browsers: [isCI ? 'ChromeHeadlessNoSandbox' : 'ChromeHeadless'],
    singleRun: true,
    autoWatch: false,
    // Force strictly sequential execution (one browser, one worker)
    concurrency: 1,
    // Increase timeouts/tolerance to reduce spurious disconnects in CI and local runs
    browserNoActivityTimeout: 60000,
    browserDisconnectTolerance: 2,
  });
};
