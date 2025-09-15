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
  plugins: ['@typescript-eslint', 'sonarjs', 'import'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:sonarjs/recommended',
  ],
  rules: {
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    'sonarjs/no-duplicate-string': 'off',
  },
  ignorePatterns: [
    'dist/**',
    'node_modules/**',
    '**/*.spec.ts',
  ],
};

