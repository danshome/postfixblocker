import {
  __setWebAuthnLoader,
  createCredential,
  getAssertion,
} from './webauthn.utility';
import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser';

describe('webauthn.util', () => {
  afterEach(() => {
    // restore default loader by pointing back to a loader that throws (so tests don't leak)
    __setWebAuthnLoader(async () => {
      throw new Error('mock reset');
    });
    // Ensure at least one explicit Jasmine expectation to avoid WARN: has no expectations
    expect().nothing();
  });

  it('createCredential delegates to startRegistration and returns its result', async () => {
    const expected = { ok: true, attObj: 'x' } as const;
    __setWebAuthnLoader(async () => ({
      /**
       * Delegate to startRegistration.
       * @param {PublicKeyCredentialCreationOptionsJSON} options - Registration options.
       * @returns {Promise<RegistrationResponseJSON & { opts: PublicKeyCredentialCreationOptionsJSON; ok: boolean; attObj: string }>} Result with echoed options for assertions.
       */
      startRegistration: async (
        options: PublicKeyCredentialCreationOptionsJSON,
      ): Promise<
        RegistrationResponseJSON & {
          opts: PublicKeyCredentialCreationOptionsJSON;
          ok: boolean;
          attObj: string;
        }
      > => ({
        ...expected,
        // Echo options to assert round-trip
        opts: options,
      }),
      /**
       * Should not be called in this branch.
       */
      startAuthentication: async (): Promise<AuthenticationResponseJSON> => {
        throw new Error('should not be called');
      },
    }));

    const result = await createCredential({
      challenge: 'abc',
    } as PublicKeyCredentialCreationOptionsJSON);
    expect((result as unknown as { ok: boolean }).ok).toBeTrue();
    expect((result as unknown as { attObj: string }).attObj).toBe('x');
    expect(
      (result as unknown as { opts: { challenge: string } }).opts.challenge,
    ).toBe('abc');
  });

  it('getAssertion delegates to startAuthentication and returns its result', async () => {
    const expected = { ok: true, asr: 'y' } as const;
    __setWebAuthnLoader(async () => ({
      /**
       * Should not be called in this branch.
       */
      startRegistration: async (): Promise<RegistrationResponseJSON> => {
        throw new Error('should not be called');
      },
      /**
       * Delegate to startAuthentication.
       * @param {PublicKeyCredentialRequestOptionsJSON} options - Authentication options.
       * @returns {Promise<AuthenticationResponseJSON & { opts: PublicKeyCredentialRequestOptionsJSON; ok: boolean; asr: string }>} Result with echoed options for assertions.
       */
      startAuthentication: async (
        options: PublicKeyCredentialRequestOptionsJSON,
      ): Promise<
        AuthenticationResponseJSON & {
          opts: PublicKeyCredentialRequestOptionsJSON;
          ok: boolean;
          asr: string;
        }
      > => ({
        ...expected,
        // Echo options to assert round-trip
        opts: options,
      }),
    }));

    const result = await getAssertion({
      challenge: 'def',
    } as PublicKeyCredentialRequestOptionsJSON);
    expect((result as unknown as { ok: boolean }).ok).toBeTrue();
    expect((result as unknown as { asr: string }).asr).toBe('y');
    expect(
      (result as unknown as { opts: { challenge: string } }).opts.challenge,
    ).toBe('def');
  });

  it('createCredential surfaces a friendly error if loader rejects', async () => {
    __setWebAuthnLoader(async () => {
      throw new Error('boom');
    });
    await expectAsync(
      createCredential({} as unknown as PublicKeyCredentialCreationOptionsJSON),
    ).toBeRejectedWithError(/registration is not available/i);
  });

  it('getAssertion surfaces a friendly error if loader rejects', async () => {
    __setWebAuthnLoader(async () => {
      throw new Error('boom');
    });
    await expectAsync(
      getAssertion({} as unknown as PublicKeyCredentialRequestOptionsJSON),
    ).toBeRejectedWithError(/authentication is not available/i);
  });
});
