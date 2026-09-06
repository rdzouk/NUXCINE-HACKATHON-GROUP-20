import { useNavigate } from 'react-router-dom';

export default function SearchingDriverPage() {
  const navigate = useNavigate();

  return (
    <main className="app-shell centered">
      <div className="pulse-dot" />
      <h2>Looking for a driver...</h2>
      <p>This won't take long.</p>
      {/* Stub button — real flow auto-advances when a driver accepts */}
      <button className="secondary-button" onClick={() => navigate('/passenger/ride')}>
        (Dev) Simulate driver found
      </button>
    </main>
  );
}