// ESLint flat config for Playwright e2e tests: enforce at least one expect()
const tsParser = require('@typescript-eslint/parser');
const jestPlugin = require('eslint-plugin-jest');

module.exports = [
  {
    files: ['e2e/**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: 'module', ecmaVersion: 2022 },
    },
    plugins: { jest: jestPlugin },
    rules: {
      'jest/expect-expect': 'error',
    },
  },
];

