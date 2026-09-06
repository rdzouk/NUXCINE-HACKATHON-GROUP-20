import { useEffect, useRef } from 'react';
import mapboxgl from '../services/mapboxClient';

export default function DriverMarker({ map, position }) {
  const markerRef = useRef(null);

  useEffect(() => {
    if (!map || !position) return;
    if (!markerRef.current) {
      const el = document.createElement('div');
      el.className = 'driver-marker'; // style as a car icon in CSS
      markerRef.current = new mapboxgl.Marker(el).setLngLat([position.lng, position.lat]).addTo(map);
    } else {
      markerRef.current.setLngLat([position.lng, position.lat]);
    }
  }, [map, position]);

  useEffect(() => () => markerRef.current?.remove(), []);

  return null;
}
