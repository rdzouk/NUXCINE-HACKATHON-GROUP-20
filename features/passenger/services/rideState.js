const PENDING_BOOKING_KEY = 'pending_booking';
const ACTIVE_RIDE_KEY = 'active_ride';
const BOOKING_ATTEMPT_KEY = 'booking_attempt';

export function getPendingBooking() {
  const raw = sessionStorage.getItem(PENDING_BOOKING_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(PENDING_BOOKING_KEY);
    return null;
  }
}

export function setPendingBooking(booking) {
  sessionStorage.setItem(PENDING_BOOKING_KEY, JSON.stringify(booking));
}

export function clearPendingBooking() {
  sessionStorage.removeItem(PENDING_BOOKING_KEY);
}

export function getBookingAttempt() {
  const raw = sessionStorage.getItem(BOOKING_ATTEMPT_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(BOOKING_ATTEMPT_KEY);
    return null;
  }
}

export function setBookingAttempt(attempt) {
  sessionStorage.setItem(BOOKING_ATTEMPT_KEY, JSON.stringify(attempt));
}

export function clearBookingAttempt() {
  sessionStorage.removeItem(BOOKING_ATTEMPT_KEY);
}

export function getActiveRide() {
  const raw = sessionStorage.getItem(ACTIVE_RIDE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(ACTIVE_RIDE_KEY);
    return null;
  }
}

export function setActiveRide(ride) {
  sessionStorage.setItem(ACTIVE_RIDE_KEY, JSON.stringify(ride));
}

export function clearActiveRide() {
  sessionStorage.removeItem(ACTIVE_RIDE_KEY);
}

