import { apiFetch } from '../../map/services/apiClient';
import { storeSession } from './session';

export function requestOtp(phone) {
  return apiFetch('/auth/otp/request', {
    method: 'POST',
    body: JSON.stringify({ phone }),
  });
}

export async function verifyOtp(challengeId, code) {
  const session = await apiFetch('/auth/otp/verify', {
    method: 'POST',
    body: JSON.stringify({
      challenge_id: challengeId,
      code,
    }),
  });

  storeSession(session);
  return session;
}


/**
 * The last OTP the server sent to this number, when there is no SMS gateway.
 *
 * Development only. The route lives on the API's dev router, which is not
 * registered unless DEBUG is on outside production, so on a real deployment
 * this returns 404 and the caller shows nothing. Never let it throw: a missing
 * convenience must not break the login screen.
 */
export async function peekOtp(phone) {
  try {
    const result = await apiFetch(`/dev/otp/${encodeURIComponent(phone)}`);
    return result?.code ?? null;
  } catch {
    return null;
  }
}
