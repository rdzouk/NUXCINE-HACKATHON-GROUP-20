import { apiFetch } from '../../map/services/apiClient';

export function createRide({ quoteId, seats, idempotencyKey }) {
  return apiFetch('/rides', {
	method: 'POST',
	headers: {
	  'Idempotency-Key': idempotencyKey,
	},
	body: JSON.stringify({
	  quote_id: quoteId,
	  seats,
	}),
  });
}

export function getRide(rideId) {
  return apiFetch(`/rides/${rideId}`);
}

export function listRides(params = {}) {
  const query = new URLSearchParams();

  if (params.status) {
	query.set('status', params.status);
  }

  if (params.limit) {
	query.set('limit', String(params.limit));
  }

  const suffix = query.toString() ? `?${query.toString()}` : '';
  return apiFetch(`/rides${suffix}`);
}

/**
 * Cancel a ride. The server decides whether a fee applies, never the client.
 *
 * A fee is charged only once a driver has been assigned and has actually moved
 * toward the pickup, which the server checks against its own trace. So the
 * amount cannot be predicted here and must be read from the response.
 */
export function cancelRide(rideId, reason) {
  return apiFetch(`/rides/${rideId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/** What this passenger owes from earlier cancellations. Blocks new bookings. */
export function getBalance() {
  return apiFetch('/me/balance');
}

/**
 * Mint a share link. Signed, expiring and revocable server-side.
 *
 * The recipient needs no account and sees a deliberately thin view: position,
 * vehicle and the driver's first name, never identity, fare or phone number.
 */
export function shareRide(rideId) {
  return apiFetch(`/rides/${rideId}/share`, { method: 'POST' });
}

/** Kill every share link for this ride, before its signature would lapse. */
export function revokeShare(rideId) {
  return apiFetch(`/rides/${rideId}/share`, { method: 'DELETE' });
}

/**
 * Send one of the fixed message templates.
 *
 * A closed set, not free text: it replaces phone contact without becoming a
 * channel for harassment, and it works on a bad network because the payload is
 * an enum rather than a string.
 */
export function sendRideMessage(rideId, templateKey) {
  return apiFetch(`/rides/${rideId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ template_key: templateKey }),
  });
}

/** Raise an SOS. Seals an immutable evidence snapshot server-side. */
export function raiseSos(rideId) {
  return apiFetch(`/rides/${rideId}/sos`, { method: 'POST' });
}
