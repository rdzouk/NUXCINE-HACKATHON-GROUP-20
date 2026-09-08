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


/**
 * Go on duty at a position, with a declared number of free seats.
 *
 * This is what actually makes a driver matchable: the matcher selects from
 * `driver_presence` joined to online drivers, so a client-side "Available"
 * flag that never reaches the server means the driver waits for offers that
 * are never sent to them.
 */
export function goOnline({ lat, lng, seatsFree = 4 }) {
  return apiFetch('/driver/online', {
    method: 'POST',
    body: JSON.stringify({ lat, lng, seats_free: seatsFree }),
  });
}

export function goOffline() {
  return apiFetch('/driver/offline', { method: 'POST' });
}

/** The driver's own profile, including KYC state. */
export function getDriverStatus() {
  return apiFetch('/driver/kyc');
}
