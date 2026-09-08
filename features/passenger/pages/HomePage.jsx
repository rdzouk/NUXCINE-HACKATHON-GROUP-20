import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAccessToken, getStoredUser } from '../../auth/services/session';
import BottomNav from '../components/BottomNav';
import NotificationBell from '../../shared/components/NotificationBell';
import Icon from '../../shared/components/Icon';
import { getLocale } from '../../shared/services/locale';
import { getBalance, listRides } from '../services/ridesApi';

/**
 * The screen everything starts from.
 *
 * It was a heading and one link, which left the first screen after login
 * almost blank. What belongs here is what a passenger opens the app to do:
 * go somewhere they have been before, in one tap, or search for somewhere new.
 *
 * Recent destinations come from the passenger's own completed rides rather
 * than from a saved-places table nobody fills in. The data already exists, and
 * a list that populates itself is worth more than an empty one waiting to be
 * curated.
 */
export default function HomePage() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const locale = getLocale();
  const [recent, setRecent] = useState([]);
  const [owed, setOwed] = useState(0);

  useEffect(() => {
    if (!getAccessToken()) {
      navigate('/login', { replace: true });
      return;
    }

    listRides({ limit: 12 })
      .then((data) => {
        // Distinct destinations, newest first. A passenger who takes the same
        // trip daily should see one entry, not twelve.
        const seen = new Set();
        const places = [];
        // `items`, not `rides`. It was the latter, which is silently empty
        // rather than an error, so this list never appeared and the screen
        // looked like it had no history to show.
        for (const ride of data.items ?? []) {
          const label = ride.dropoff?.label;
          if (!label || seen.has(label)) continue;
          seen.add(label);
          places.push({ id: ride.id, label, fare: ride.final_fare_xaf });
          if (places.length === 4) break;
        }
        setRecent(places);
      })
      .catch(() => setRecent([]));

    getBalance()
      .then((b) => setOwed(b.outstanding_xaf ?? 0))
      .catch(() => setOwed(0));
  }, [navigate]);

  const firstName = (user?.display_name ?? '').split(' ')[0];
  const greeting = locale === 'en' ? 'Hello' : 'Bonjour';

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">
            {greeting}, {firstName || (locale === 'en' ? 'there' : 'a vous')}
          </p>
          <h1 className="headline">
            {locale === 'en' ? 'Where to?' : 'On va ou ?'}
          </h1>
        </div>
        <NotificationBell />
      </header>

      {owed > 0 ? (
        <p className="balance-banner">
          {locale === 'en'
            ? `You owe ${owed.toLocaleString()} FCFA from a cancelled ride. Settle it with your driver to book again.`
            : `Vous devez ${owed.toLocaleString()} FCFA suite a une annulation. Reglez avec votre chauffeur pour reserver a nouveau.`}
        </p>
      ) : null}

      {/* The search bar is the primary action, so it looks like a field rather
          than a link and sits above everything else. */}
      <button
        type="button"
        className="home-search"
        onClick={() => navigate('/passenger/book')}
      >
        <Icon name="search" />
        <span>
          {locale === 'en' ? 'Enter your destination' : 'Entrez votre destination'}
        </span>
      </button>

      <p className="eyebrow">
        {locale === 'en' ? 'Quick destinations' : 'Destinations rapides'}
      </p>

      <div className="place-tiles">
        <button
          type="button"
          className="place-tile"
          onClick={() => navigate('/passenger/book')}
        >
          <Icon name="home" />
          <span>{locale === 'en' ? 'Home' : 'Domicile'}</span>
        </button>
        <button
          type="button"
          className="place-tile"
          onClick={() => navigate('/passenger/book')}
        >
          <Icon name="work" />
          <span>{locale === 'en' ? 'Work' : 'Travail'}</span>
        </button>
        <button
          type="button"
          className="place-tile"
          onClick={() => navigate('/passenger/book')}
        >
          <Icon name="airport" />
          <span>{locale === 'en' ? 'Airport' : 'Aeroport'}</span>
        </button>
      </div>

      {recent.length > 0 ? (
        <>
          <p className="eyebrow">
            {locale === 'en' ? 'Recent trips' : 'Trajets recents'}
          </p>
          <ul className="recent-list">
            {recent.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => navigate('/passenger/book')}>
                  <span className="recent-list__icon">
                    <Icon name="clock" />
                  </span>
                  <span className="recent-list__body">
                    <span className="recent-list__label">{r.label}</span>
                    {r.fare ? (
                      <span className="recent-list__fare">
                        {r.fare.toLocaleString()} FCFA
                      </span>
                    ) : null}
                  </span>
                  <Icon name="arrow" size={16} />
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <BottomNav />
    </main>
  );
}
