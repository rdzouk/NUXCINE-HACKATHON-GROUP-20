import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function RideInProgressPage() {
  const [pin, setPin] = useState('');
  const [started, setStarted] = useState(false);
  const navigate = useNavigate();

  return (
    <main className="app-shell centered">
      {!started ? (
        <>
          <h2>Enter passenger PIN to start</h2>
          <input value={pin} onChange={(e) => setPin(e.target.value)} maxLength={4} placeholder="4-digit PIN" />
          <button className="primary-button" onClick={() => setStarted(true)}>Start ride</button>
        </>
      ) : (
        <>
          <h2>Ride in progress</h2>
          <p>Heading to Total Nsimeyong</p>
          <button className="primary-button" onClick={() => navigate('/driver/end')}>End ride</button>
        </>
      )}
    </main>
  );
}