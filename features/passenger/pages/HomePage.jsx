import { Link } from 'react-router-dom';
import { useMockAuth } from '../../../app/MockAuthContext';
import BottomNav from '../components/BottomNav';

export default function HomePage() {
  const { user } = useMockAuth();

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Bonjour, {user.name}</p>
          <h1>Where are you going?</h1>
        </div>
      </header>

      <Link to="/passenger/book" className="search-bar-button">
        🔍 Enter your destination
      </Link>

      <BottomNav />
    </main>
  );
}