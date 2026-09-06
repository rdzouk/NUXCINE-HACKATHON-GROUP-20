// Simple MVP pricing — tune the base/rate for your local context
const BASE_FARE = 300;      // FCFA
const RATE_PER_KM = 150;    // FCFA per km

export function estimatePrice(distanceKm) {
  return Math.round(BASE_FARE + distanceKm * RATE_PER_KM);
}