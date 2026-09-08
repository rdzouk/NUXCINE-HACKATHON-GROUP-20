import { apiFetch } from '../../map/services/apiClient';

/** The caller's own profile. */
export function getMe() {
  return apiFetch('/me');
}

/**
 * Update the profile.
 *
 * Accessibility fields here are **vehicle capability requirements**, never
 * anything about the person. "This trip needs a ramp" is a logistics fact;
 * "this passenger uses a wheelchair" would be health data, which Law 2024/017
 * prohibits processing outright (I9). The wording in the UI has to match.
 */
export function updateMe(patch) {
  return apiFetch('/me', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

/**
 * The capability vocabulary, with its labels.
 *
 * Served by the API rather than hardcoded here so a wording correction is a
 * server change instead of an app release.
 */
export function getVehicleCapabilities() {
  return apiFetch('/vehicles/capabilities');
}
