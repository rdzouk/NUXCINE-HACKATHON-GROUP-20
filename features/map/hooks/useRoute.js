import { useState, useCallback } from 'react';
import { getQuote } from '../services/directions';

export function useRoute() {
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchQuote = useCallback(async (origin, destination, seats = 1, mode = 'exclusive') => {
    setLoading(true);
    setError(null);
    try {
      const result = await getQuote(origin, destination, seats, mode);
      setQuote(result);
    } catch (err) {
      // No client-side fallback price here — a failed quote must not be
      // guessed at (I2). Show the error, let the user retry.
      setError(err.message);
      setQuote(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return { quote, loading, error, fetchQuote };
}