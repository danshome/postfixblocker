/* ESLint configuration for Angular (TypeScript) without a server.
 * Uses TypeScript ESLint + sonarjs rules for maintainability.
 */
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: 'tsconfig.json',
    sourceType: 'module',
    ecmaVersion: 2022,
  },
  env: {
    browser: true,
    es2022: true,
    node: false,
  },
  plugins: ['@typescript-eslint', 'sonarjs', 'import', 'jest'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:sonarjs/recommended',
  ],
  rules: {
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
  },
  ignorePatterns: [
    'dist/**',
    'node_modules/**',
    // Ignore unit specs under src, but keep Playwright e2e specs included
    'src/**/*.spec.ts',
  ],
  overrides: [
    {
      files: ['e2e/**/*.ts'],
      rules: {
        // Enforce at least one expect() per Playwright test file/spec
        'jest/expect-expect': 'error',
      },
    },
  ],
};
