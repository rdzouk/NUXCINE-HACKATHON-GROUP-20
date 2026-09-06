import { useState } from 'react';
import { Link } from 'react-router-dom';

export default function DashboardPage() {
  const [available, setAvailable] = useState(false);

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Driver dashboard</h1>
        <button
          className={available ? 'status-pill status-pill--on' : 'status-pill'}
          onClick={() => setAvailable((v) => !v)}
        >
          {available ? 'Available' : 'Offline'}
        </button>
      </header>

      {available ? (
        <p>Waiting for ride requests...</p>
      ) : (
        <p>Go online to start receiving requests.</p>
      )}

      <Link to="/driver/request" className="secondary-button">
        Preview: incoming request screen
      </Link>
    </main>
  );
}