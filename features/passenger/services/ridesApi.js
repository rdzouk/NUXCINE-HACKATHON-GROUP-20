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
