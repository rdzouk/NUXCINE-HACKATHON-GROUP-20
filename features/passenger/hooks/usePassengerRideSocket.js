import { useEffect, useRef, useState } from 'react';
import { clearSession, getAccessToken } from '../../auth/services/session';
import { getRide } from '../services/ridesApi';
import { getActiveRide, setActiveRide } from '../services/rideState';
import { wsBaseUrl } from '../../shared/services/wsUrl';

export function usePassengerRideSocket(rideId) {
  const [ride, setRide] = useState(() => getActiveRide());
  const [status, setStatus] = useState(() => getActiveRide()?.status ?? null);
  const [driverLocation, setDriverLocation] = useState(() => getActiveRide()?.driver_location ?? null);
  const [error, setError] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    if (!rideId) {
      return;
    }

    let isMounted = true;

    async function syncRide() {
      try {
        const data = await getRide(rideId);

        if (!isMounted) {
          return;
        }

        setRide(data.ride);
        setStatus(data.ride.status);
        setDriverLocation(data.ride.driver_location ?? null);
        setActiveRide(data.ride);
      } catch (err) {
        if (isMounted) {
          setError(err.message);
        }
      }
    }

    syncRide();

    const token = getAccessToken();

    if (!token) {
      setError('Your session has expired. Please log in again.');
      return () => {
        isMounted = false;
      };
    }

    const ws = new WebSocket(`${wsBaseUrl()}/ws/passenger`);
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

      if (msg.type === 'error') {
        setError(msg.message ?? 'Socket error');
        return;
      }

      if (msg.type === 'ready') {
        if (!msg.ride_id || msg.ride_id === rideId) {
          setStatus(msg.ride_status ?? status);
          syncRide();
        }
        return;
      }

      if (msg.type === 'ride_update') {
        if (!msg.ride_id || msg.ride_id === rideId) {
          setStatus(msg.status ?? status);
          syncRide();
        }
        return;
      }

      if (msg.type === 'driver_location' && msg.ride_id === rideId && msg.location) {
        setDriverLocation(msg.location);
      }
    };

    ws.onclose = (event) => {
      if (event.code === 1008) {
        clearSession();
        window.location.assign('/login');
      }
    };

    return () => {
      isMounted = false;
      ws.close();
    };
  }, [rideId]);

  return {
    ride,
    status,
    driverLocation,
    error,
  };
}

