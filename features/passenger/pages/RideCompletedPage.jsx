import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMockAuth } from '../../shared/context/MockAuthContext';

export default function RideCompletedPage() {
  const { ride } = useMockAuth();
  const [rating, setRating] = useState(0);
  const navigate = useNavigate();

  return (
    <main className="app-shell centered">
      <h1>Ride completed</h1>
      <p>Fare: {ride.fareXaf.toLocaleString()} FCFA</p>

      <div className="stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} onClick={() => setRating(n)} className={n <= rating ? 'star star--filled' : 'star'}>★</span>
        ))}
      </div>

      <button className="primary-button" onClick={() => navigate('/passenger/home')}>
        Done
      </button>
    </main>
  );
}