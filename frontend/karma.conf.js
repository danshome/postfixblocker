// Karma configuration for Angular 20 + Jasmine
module.exports = function (config) {
  // Prefer Playwright Chromium if available to ensure headless runs without a system Chrome
  try {
    process.env.CHROME_BIN = require('playwright-core').chromium.executablePath();
  } catch (e) {
    // fallback to system Chrome
  }
  // Enforce coverage thresholds; can override via env FE_COV_MIN or COVERAGE_MIN_FE
  const FE_MIN = parseInt(process.env.FE_COV_MIN || process.env.COVERAGE_MIN_FE || '80', 10) || 0;
  config.set({
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
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
      reporters: [{ type: 'html' }, { type: 'text-summary' }],
      check: {
        global: {
          statements: FE_MIN,
          lines: FE_MIN,
          functions: FE_MIN,
          branches: FE_MIN,
        },
      },
    },
    browsers: ['ChromeHeadless'],
    singleRun: true,
    autoWatch: false,
  });
};
