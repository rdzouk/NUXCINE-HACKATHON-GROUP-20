import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getAccessToken, getStoredUser } from '../../auth/services/session';
import BottomNav from '../components/BottomNav';
import NotificationBell from '../../shared/components/NotificationBell';

export default function HomePage() {
  const navigate = useNavigate();
  const user = getStoredUser();

  useEffect(() => {
    if (!getAccessToken()) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Bonjour, {user?.display_name ?? 'there'}</p>
          <h1>Where are you going?</h1>
        </div>
        <NotificationBell />
      </header>

      <Link to="/passenger/book" className="search-bar-button">
        Enter your destination
      </Link>

      <BottomNav />
    </main>
  );
}