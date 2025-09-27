// Lightweight WebAuthn helpers around @simplewebauthn/browser
// Intentionally optional: if the library is missing at runtime, functions will reject gracefully.
// Testability: allow injecting a loader so unit tests can mock the dynamic import.

import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser';

interface WebAuthnBrowserModule {
  startRegistration: (
    options: PublicKeyCredentialCreationOptionsJSON,
  ) => Promise<RegistrationResponseJSON>;
  startAuthentication: (
    options: PublicKeyCredentialRequestOptionsJSON,
  ) => Promise<AuthenticationResponseJSON>;
}

/**
 * Dynamically loaded module factory for @simplewebauthn/browser.
 * Tests may override via __setWebAuthnLoader to inject a mock module.
 * @returns {Promise<WebAuthnBrowserModule>} Promise resolving to the browser module.
 */
let _loader: () => Promise<WebAuthnBrowserModule> = () =>
  import(
    '@simplewebauthn/browser'
  ) as unknown as Promise<WebAuthnBrowserModule>;

// Internal helper to set a custom loader (used by unit tests)
/**
 * Override the dynamic import loader used for WebAuthn to facilitate unit testing.
 * @param {() => Promise<WebAuthnBrowserModule>} function_ - Function that returns the WebAuthn browser module.
 * @returns {void} Nothing.
 */
export function __setWebAuthnLoader(
  function_: () => Promise<WebAuthnBrowserModule>,
): void {
  _loader = function_;
}

/**
 * Begin a WebAuthn registration ceremony by delegating to the browser helper.
 * @param {PublicKeyCredentialCreationOptionsJSON} options - Options provided by the backend challenge.
 * @returns {Promise<RegistrationResponseJSON>} Registration response produced by the browser.
 */
export async function createCredential(
  options: PublicKeyCredentialCreationOptionsJSON,
): Promise<RegistrationResponseJSON> {
  try {
    const module_ = await _loader();
    return await module_.startRegistration(options);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error('WebAuthn registration is not available: ' + message);
  }
}

/**
 * Begin a WebAuthn authentication ceremony by delegating to the browser helper.
 * @param {PublicKeyCredentialRequestOptionsJSON} options - Options provided by the backend challenge.
 * @returns {Promise<AuthenticationResponseJSON>} Authentication response produced by the browser.
 */
export async function getAssertion(
  options: PublicKeyCredentialRequestOptionsJSON,
): Promise<AuthenticationResponseJSON> {
  try {
    const module_ = await _loader();
    return await module_.startAuthentication(options);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error('WebAuthn authentication is not available: ' + message);
  }
}
