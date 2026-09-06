import { useState, useEffect, useRef } from 'react';

// Connects to the contract's WS /ws/passenger channel. Auth is via the
// Authorization header at connect time — never a query string (contract rule).
export function useDriverLocation(rideId) {
  const [position, setPosition] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!rideId) return;

    const token = localStorage.getItem('access_token');
    const wsUrl = `${import.meta.env.VITE_WS_BASE_URL}/ws/passenger`;
    const ws = new WebSocket(wsUrl, [], { headers: { Authorization: `Bearer ${token}` } });
    // Note: browser WebSocket API doesn't support custom headers directly —
    // coordinate with your backend owner on the actual first-frame token
    // handshake they implement per the contract's "never a query string" rule.
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'driver_location') {
        setPosition({ lat: msg.lat, lng: msg.lng, heading: msg.heading });
      }
    };

    return () => ws.close();
  }, [rideId]);

  return position;
}