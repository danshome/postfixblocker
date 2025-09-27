import eslint from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import angular from "angular-eslint";
import prettier from "eslint-plugin-prettier";
import prettierConfig from "eslint-config-prettier";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import sonarjs from "eslint-plugin-sonarjs";
import pluginSecurity from "eslint-plugin-security";
import jsdoc from "eslint-plugin-jsdoc";
import pluginPromise from "eslint-plugin-promise";
import playwright from "eslint-plugin-playwright";
import boundaries from 'eslint-plugin-boundaries'

// Boundary-aware Angular layout we’re enforcing:
//
// src/app/core/**         -> "core"    (singletons, interceptors, tokens)
// src/app/shared/**       -> "shared"  (reusable ui/pipes/directives)
// src/app/features/*/**   -> "feature" (each folder is an isolated feature)
// src/app/pages/*/**      -> "page"    (route-level compositions; optional)
// src/app/**              -> "app"     (bootstrap and top wiring)
// src/environments/**     -> "env"     (environment files)
// **/*.spec.ts            -> "tests"   (unit tests)

export default tseslint.config(
  {
    files: ["**/*.ts"],
    extends: [
      eslintPluginUnicorn.configs.recommended,
      eslint.configs.recommended,
      ...tseslint.configs.recommended,
      ...tseslint.configs.stylistic,
      ...angular.configs.tsRecommended,
      prettierConfig,
      sonarjs.configs.recommended,
      pluginSecurity.configs.recommended,
      jsdoc.configs["flat/recommended"],
      pluginPromise.configs["flat/recommended"],
    ],
    processor: angular.processInlineTemplates,
    languageOptions: {
      globals: {
        ...globals.builtin,
        ...globals.browser,
      },
    },
    settings: {
      // Let boundaries (via eslint-module-utils) resolve TS paths like "@app/*"
      "import/resolver": {
        "eslint-import-resolver-typescript": {
          project: true,
        },
        node: true,
      },
      // Most-specific first (plugin matches from right to left)
      "boundaries/elements": [
        {
          type: "feature",
          basePattern: "src/app",
          pattern: "features/*",
          mode: "folder",
        },
        {
          type: "shared",
          basePattern: "src/app",
          pattern: "shared",
          mode: "folder",
        },
        {
          type: "core",
          basePattern: "src/app",
          pattern: "core",
          mode: "folder",
        },
        {
          type: "page",
          basePattern: "src/app",
          pattern: "pages/*",
          mode: "folder",
        },
        {
          type: "app",
          basePattern: "src",
          pattern: "app",
          mode: "folder",
        },
        {
          type: "env",
          basePattern: "src",
          pattern: "environments/*",
          mode: "folder",
        },
        {
          type: "tests",
          pattern: ["**/*.spec.ts", "**/*.test.ts"],
          mode: "file",
        },
        {
          // Allow TypeScript ambient type declarations that support tooling/config code
          type: "types",
          basePattern: "src",
          pattern: "types",
          mode: "folder",
        },
        {
          // Bootstrap/root TS entry files that are not inside src/app
          type: "bootstrap",
          pattern: ["src/test.ts", "src/main.ts"],
          mode: "file",
        },
      ],
    },
    plugins: {
      prettier,
      eslintPluginUnicorn,
      pluginSecurity,
      jsdoc,
      pluginPromise,
      eslint, // (kept from your original file)
      boundaries, // ⬅️ NEW
    },
    rules: {
      // Start from the plugin's recommended set, then tighten with project rules
      ...boundaries.configs.recommended.rules, // ⬅️ NEW baseline

      // Angular selectors
      "@angular-eslint/directive-selector": [
        "error",
        { type: "attribute", prefix: "app", style: "camelCase" },
      ],
      "@angular-eslint/component-selector": [
        "error",
        { type: "element", prefix: "app", style: "kebab-case" },
      ],

      // Formatting & module system hygiene
      "prettier/prettier": "error",
      "@typescript-eslint/no-require-imports": "error",
      "@typescript-eslint/no-var-requires": "error",

      // 🔒 Architectural boundaries
      // Every TS file must belong to one of the defined element types
      "boundaries/no-unknown-files": "error",

      // Feature isolation and layering:
      // - core/shared can depend on each other, but not on features/pages/app
      // - features can depend on shared/core and on *their own* feature folder
      // - pages can depend on features/shared/core
      // - app can depend on anything app-level plus features/shared/core
      "boundaries/element-types": [
        "error",
        {
          default: "disallow",
          rules: [
            { from: "core", allow: ["core", "shared"] },
            { from: "shared", allow: ["shared", "core"] },
            {
              // Allow a feature to import within its own folder,
              // but forbid importing *other* features
              from: ["feature"],
              allow: [
                "shared",
                "core",
                ["feature", { elementName: "${from.elementName}" }],
              ],
            },
            { from: "page", allow: ["feature", "shared", "core"] },
            { from: "app", allow: ["app", "feature", "shared", "core"] },
            {
              from: "tests",
              allow: ["feature", "shared", "core", "app", "env"],
            },
          ],
        },
      ],

      // If you later want to enforce "only import other elements via their entry file"
      // uncomment and adapt this to your chosen entry names (index.ts or public-api.ts):
      // "boundaries/entry-point": [
      //   "error",
      //   {
      //     default: "allow",
      //     rules: [
      //       { target: "feature", allow: ["index.ts", "public-api.ts"] },
      //       { target: "shared", allow: ["index.ts", "public-api.ts"] },
      //       { target: "core", allow: ["index.ts"] },
      //     ],
      //   },
      // ],
    },
  },

  // Angular templates
  {
    files: ["**/*.html"],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
    rules: {},
  },

  // E2E/Playwright: keep boundaries relaxed here
  {
    files: ["e2e/**/*.ts", "global-setup.ts", "playwright.config.ts"],
    ...playwright.configs["flat/recommended"],
    languageOptions: {
      globals: { ...globals.node },
    },
    rules: {
      "boundaries/*": "off",
    },
  }
);
