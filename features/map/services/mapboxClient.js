import mapboxgl from 'mapbox-gl';

const token = import.meta.env.VITE_MAPBOX_TOKEN;

/**
 * Whether a map can be drawn at all.
 *
 * Exported so callers can decide before constructing a Map, because Mapbox GL
 * throws on construction without a token and an uncaught throw in a child
 * takes down the whole screen. Checking first turns a white page into a
 * labelled panel.
 *
 * Only a public `pk.` token belongs here. It ships in the browser bundle by
 * design, which is what a publishable token is for, and it must be
 * URL-restricted in the Mapbox dashboard. A secret `sk.` token in a client
 * bundle is a credential leak, so one is refused outright rather than
 * quietly used.
 */
export const hasMapboxToken = Boolean(token) && token.startsWith('pk.');

if (token && !token.startsWith('pk.')) {
  // Loud, because the failure mode of shipping a secret key is silent.
  console.error(
    'VITE_MAPBOX_TOKEN must be a public pk. token. Ignoring the configured ' +
      'value: a secret sk. token must never reach the browser bundle.',
  );
}

if (hasMapboxToken) {
  mapboxgl.accessToken = token;
}

export const MAP_DEFAULTS = {
  style: 'mapbox://styles/mapbox/streets-v12',
  zoom: 14,
};

export default mapboxgl;
