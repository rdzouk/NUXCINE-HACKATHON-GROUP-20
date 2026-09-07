import { useState, useEffect, useRef } from 'react';

// Connects to WS /ws/passenger with first-frame auth from the integration contract.
export function useDriverLocation(rideId) {
  const [position, setPosition] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!rideId) return;

    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`${import.meta.env.VITE_WS_BASE_URL}/ws/passenger`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
        return;
      }

      if (msg.type === 'driver_location' && msg.ride_id === rideId && msg.location) {
        setPosition(msg.location);
      }
    };

    return () => ws.close();
  }, [rideId]);

  return position;
}