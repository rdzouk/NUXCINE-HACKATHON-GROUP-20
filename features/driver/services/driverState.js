const ACTIVE_OFFER_KEY = 'driver_active_offer';
const ACTIVE_RIDE_KEY = 'driver_active_ride';
const COMPLETED_RIDE_KEY = 'driver_completed_ride';
const DUTY_KEY = 'driver_duty_state';

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

/**
 * Whether this driver put themselves on duty.
 *
 * Kept in `localStorage`, not `sessionStorage`, because being on duty outlives
 * a tab: a driver who closes the app is still online, still in the matcher,
 * and still being sent work. The dashboard read its duty state from React
 * state alone, so a reload showed "Off duty" above a list of incoming
 * requests, which is the screen contradicting itself.
 *
 * A hint, not the truth. The server decides who is online; there is no read
 * endpoint for presence yet, so this remembers what this device asked for and
 * the offer list is what confirms it.
 */
export function getDutyState() {
  try {
    return localStorage.getItem(DUTY_KEY) === 'on';
  } catch {
    return false;
  }
}

export function setDutyState(isOn) {
  try {
    localStorage.setItem(DUTY_KEY, isOn ? 'on' : 'off');
  } catch {
    /* private mode: the toggle simply does not survive a reload */
  }
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

