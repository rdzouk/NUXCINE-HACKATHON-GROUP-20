import { useEffect, useRef, useState } from 'react';
import mapboxgl, { MAP_DEFAULTS, hasMapboxToken } from '../services/mapboxClient';

/**
 * The map, and what to show when there cannot be one.
 *
 * Mapbox GL throws on construction if no access token is set, and an
 * uncaught throw in a child takes the whole screen down. That is the wrong
 * failure: the booking screen's actual work, searching landmarks, choosing
 * exclusive or shared, and reading a server-computed fare, needs no map at
 * all. Losing the tiles should cost the tiles.
 *
 * So a missing or rejected token renders a labelled panel instead. It says
 * what is missing and what still works, because a blank grey rectangle during
 * a demo reads as "broken" when the truth is "one environment variable is not
 * set".
 */
export default function MapView({ center, children }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!center || mapRef.current || !hasMapboxToken) return undefined;

    try {
      mapRef.current = new mapboxgl.Map({
        container: containerRef.current,
        style: MAP_DEFAULTS.style,
        center: [center.lng, center.lat],
        zoom: MAP_DEFAULTS.zoom,
      });

      // A bad or restricted token fails asynchronously, after construction
      // succeeded, so the error event has to be caught as well.
      mapRef.current.on('error', () => setFailed(true));
    } catch {
      setFailed(true);
    }

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [center]);

  if (!hasMapboxToken || failed) {
    return (
      <div className="map-placeholder">
        <p className="map-placeholder__title">Map unavailable</p>
        <p className="map-placeholder__note">
          {hasMapboxToken
            ? 'The map could not load.'
            : 'No map key is configured (VITE_MAPBOX_TOKEN).'}{' '}
          Everything else on this screen works: search, fares and booking are
          served by the API, not by the map.
        </p>
        {center ? (
          <p className="map-placeholder__coords">
            {center.lat.toFixed(4)}, {center.lng.toFixed(4)}
          </p>
        ) : null}
        {children}
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      {children}
    </div>
  );
}
