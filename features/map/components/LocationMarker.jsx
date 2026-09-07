import { useEffect, useRef } from 'react';
import mapboxgl from '../services/mapboxClient';

export default function LocationMarker({ map, position }) {
  const markerRef = useRef(null);

  useEffect(() => {
    if (!map || !position) return;

    if (!markerRef.current) {
      const el = document.createElement('div');
      el.className = 'user-location-marker'; // style as a blue dot in CSS
      markerRef.current = new mapboxgl.Marker({ color: '#2563eb' })
        .setLngLat([position.lng, position.lat])
        .addTo(map);

      // Center the map on the user's first known position
      map.flyTo({ center: [position.lng, position.lat], zoom: 15 });
    } else {
      markerRef.current.setLngLat([position.lng, position.lat]);
    }
  }, [map, position]);

  useEffect(() => () => markerRef.current?.remove(), []);

  return null; // draws directly on the map instance, no DOM output
}