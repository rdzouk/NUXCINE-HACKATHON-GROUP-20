import { useEffect, useRef } from 'react';
import mapboxgl, { MAP_DEFAULTS } from '../services/mapboxClient';

export default function MapView({ center, children }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!center || mapRef.current) return;
    mapRef.current = new mapboxgl.Map({
      container: containerRef.current,
      style: MAP_DEFAULTS.style,
      center: [center.lng, center.lat],
      zoom: MAP_DEFAULTS.zoom,
    });
  }, [center]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }}>{children}</div>;
}