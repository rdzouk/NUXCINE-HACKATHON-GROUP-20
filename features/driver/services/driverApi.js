import { apiFetch } from '../../map/services/apiClient';

export function listDriverOffers() {
  return apiFetch('/driver/offers');
}

export function acceptDriverOffer(offerId) {
  return apiFetch(`/driver/offers/${offerId}/accept`, {
    method: 'POST',
  });
}

export function declineDriverOffer(offerId) {
  return apiFetch(`/driver/offers/${offerId}/decline`, {
    method: 'POST',
  });
}

export function getDriverRide(rideId) {
  return apiFetch(`/rides/${rideId}`);
}

export function markDriverArrived(rideId) {
  return apiFetch(`/rides/${rideId}/arrived`, {
    method: 'POST',
  });
}

export function startDriverRide(rideId, pin) {
  return apiFetch(`/rides/${rideId}/start`, {
    method: 'POST',
    body: JSON.stringify({ pin }),
  });
}

export function completeDriverRide(rideId) {
  return apiFetch(`/rides/${rideId}/complete`, {
    method: 'POST',
  });
}

