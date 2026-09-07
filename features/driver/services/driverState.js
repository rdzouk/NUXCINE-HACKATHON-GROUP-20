const ACTIVE_OFFER_KEY = 'driver_active_offer';
const ACTIVE_RIDE_KEY = 'driver_active_ride';
const COMPLETED_RIDE_KEY = 'driver_completed_ride';

function readJson(key) {
  const raw = sessionStorage.getItem(key);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

function writeJson(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

function clearKey(key) {
  sessionStorage.removeItem(key);
}

export function getActiveOffer() {
  return readJson(ACTIVE_OFFER_KEY);
}

export function setActiveOffer(offer) {
  writeJson(ACTIVE_OFFER_KEY, offer);
}

export function clearActiveOffer() {
  clearKey(ACTIVE_OFFER_KEY);
}

export function getActiveDriverRide() {
  return readJson(ACTIVE_RIDE_KEY);
}

export function setActiveDriverRide(ride) {
  writeJson(ACTIVE_RIDE_KEY, ride);
}

export function clearActiveDriverRide() {
  clearKey(ACTIVE_RIDE_KEY);
}

export function getCompletedDriverRide() {
  return readJson(COMPLETED_RIDE_KEY);
}

export function setCompletedDriverRide(rideSummary) {
  writeJson(COMPLETED_RIDE_KEY, rideSummary);
}

export function clearCompletedDriverRide() {
  clearKey(COMPLETED_RIDE_KEY);
}

