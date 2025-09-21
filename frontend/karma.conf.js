// Karma configuration for Angular 20 + Jasmine
module.exports = function (config) {
  // Prefer Playwright Chromium if available to ensure headless runs without a system Chrome
  try {
    process.env.CHROME_BIN = require('playwright-core').chromium.executablePath();
  } catch (e) {
    // fallback to system Chrome
  }

  const isCI = !!(process.env.CI || process.env.GITHUB_ACTIONS || process.env.CHROME_NO_SANDBOX);

  // Enforce coverage thresholds; can override via env FE_COV_MIN or COVERAGE_MIN_FE
  const FE_MIN = parseInt(process.env.FE_COV_MIN || process.env.COVERAGE_MIN_FE || '80', 10) || 0;
  const FE_BRANCH_MIN = parseInt(process.env.FE_BRANCH_MIN || process.env.COVERAGE_MIN_FE_BRANCH || String(FE_MIN), 10) || 0;

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
  });
};
