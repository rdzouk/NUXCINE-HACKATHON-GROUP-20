import { useState, useEffect } from 'react';

// rideId: which ride to watch. onSubscribe: injected by feature/driver's
// Supabase realtime channel — kept generic so feature/map has zero
// dependency on how the data arrives.
export function useDriverLocation(rideId, subscribeFn) {
  const [position, setPosition] = useState(null);

  useEffect(() => {
    if (!rideId || !subscribeFn) return;
    const unsubscribe = subscribeFn(rideId, (newPos) => setPosition(newPos));
    return () => unsubscribe?.();
  }, [rideId, subscribeFn]);

  return position;
}
