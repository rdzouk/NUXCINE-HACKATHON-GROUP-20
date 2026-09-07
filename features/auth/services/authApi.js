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

