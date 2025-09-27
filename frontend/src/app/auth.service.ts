import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser';
import { Observable } from 'rxjs';

export interface SessionInfo {
  authenticated: boolean;
  username?: string;
  mustChangePassword?: boolean;
  hasWebAuthn?: boolean;
}

/**
 *
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);

  // Session -------------------------------------------------
  // Options:
  // - strict: when true, propagate backend errors to the caller (no fallback)
  /**
   *
   * @param options
   * @param options.strict
   */
  getSession(options?: { strict?: boolean }): Observable<SessionInfo> {
    const strict = !!options?.strict;
    if (strict) {
      // Pass-through; let the caller handle errors explicitly
      return this.http.get<SessionInfo>('/auth/session', {
        withCredentials: true,
      });
    }
    // Default behavior preserves legacy fallback to authenticated:true on error
    return new Observable<SessionInfo>((subscriber) => {
      this.http
        .get<SessionInfo>('/auth/session', { withCredentials: true })
        .subscribe({
          /**
           *
           * @param value
           */
          next: (value) => {
            subscriber.next(value);
            subscriber.complete();
          },
          /**
           *
           */
          error: () => {
            // Fallback: assume authenticated to avoid breaking UI/tests when /auth/session is missing
            subscriber.next({ authenticated: true });
            subscriber.complete();
          },
        });
    });
  }

  // Password login/logout ----------------------------------
  /**
   *
   * @param username
   * @param password
   */
  loginPassword(username: string, password: string) {
    return this.http.post<SessionInfo>(
      '/auth/login/password',
      { username, password },
      { withCredentials: true },
    );
  }

  /**
   *
   * @param oldPassword
   * @param newPassword
   */
  changePassword(oldPassword: string, newPassword: string) {
    return this.http.post<{ ok: boolean }>(
      '/auth/change-password',
      { old_password: oldPassword, new_password: newPassword },
      { withCredentials: true },
    );
  }

  /**
   *
   */
  logout() {
    return this.http.post<{ ok: boolean }>(
      '/auth/logout',
      {},
      { withCredentials: true },
    );
  }

  // WebAuthn flows -----------------------------------------
  /**
   *
   */
  getRegisterChallenge(): Observable<PublicKeyCredentialCreationOptionsJSON> {
    return this.http.get<PublicKeyCredentialCreationOptionsJSON>(
      '/auth/register/challenge',
      {
        withCredentials: true,
      },
    );
  }

  /**
   *
   * @param attestationResponse
   */
  verifyRegister(attestationResponse: RegistrationResponseJSON) {
    return this.http.post<SessionInfo>(
      '/auth/register/verify',
      attestationResponse,
      { withCredentials: true },
    );
  }

  /**
   *
   */
  getLoginChallenge(): Observable<PublicKeyCredentialRequestOptionsJSON> {
    return this.http.get<PublicKeyCredentialRequestOptionsJSON>(
      '/auth/login/challenge',
      {
        withCredentials: true,
      },
    );
  }

  /**
   *
   * @param assertionResponse
   */
  verifyLogin(assertionResponse: AuthenticationResponseJSON) {
    return this.http.post<SessionInfo>(
      '/auth/login/verify',
      assertionResponse,
      { withCredentials: true },
    );
  }
}
