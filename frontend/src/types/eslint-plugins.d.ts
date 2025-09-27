interface MinimalEslintPlugin {
  readonly configs?: Record<string, unknown>;
  readonly rules?: Record<string, unknown>;
  readonly [key: string]: unknown;
}

declare module 'eslint-plugin-promise' {
  // Minimal ambient declaration to satisfy TS7016 when importing the plugin in eslint.config.mjs
  // We expose only the shape we rely on in config consumption.
  const plugin: MinimalEslintPlugin;
  export default plugin;
}

declare module 'eslint-plugin-boundaries' {
  // Minimal ambient declaration to satisfy TS7016 when importing the plugin in eslint.config.mjs
  const plugin: MinimalEslintPlugin;
  export default plugin;
}
