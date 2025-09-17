// Karma configuration for Angular 20 + Jasmine
module.exports = function (config) {
  // Prefer Playwright Chromium if available to ensure headless runs without a system Chrome
  try {
    process.env.CHROME_BIN = require('playwright-core').chromium.executablePath();
  } catch (e) {
    // fallback to system Chrome
  }
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
    },
    browsers: ['ChromeHeadless'],
    singleRun: true,
    autoWatch: false,
  });
};
