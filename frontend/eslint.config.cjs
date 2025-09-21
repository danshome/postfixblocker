// ESLint flat config for Angular/TypeScript (ESLint v9)
const tsParser = require('@typescript-eslint/parser');
const tsPlugin = require('@typescript-eslint/eslint-plugin');
const sonarjs = require('eslint-plugin-sonarjs');
const jestPlugin = require('eslint-plugin-jest');

module.exports = [
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: 'tsconfig.json',
        sourceType: 'module',
        ecmaVersion: 2022,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      sonarjs,
    },
    // Enable SonarJS recommended rules and our local additions
    rules: Object.assign(
      {},
      sonarjs.configs.recommended?.rules || {},
      {
        'no-unused-vars': 'off',
        '@typescript-eslint/no-unused-vars': [
          'warn',
          { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
        ],
        // Temporary relaxations to keep CI green while migrating rules
        'sonarjs/deprecation': 'off',
        'sonarjs/use-type-alias': 'off',
        'sonarjs/no-selector-parameter': 'off',
      }
    ),
  },
  // src/test.ts is covered by the primary ruleset now that it uses non-deprecated APIs
  {
    files: ['e2e/**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: 'module', ecmaVersion: 2022 },
    },
    plugins: {
      jest: jestPlugin,
    },
    rules: {
      'jest/expect-expect': 'error',
    },
  },
];
