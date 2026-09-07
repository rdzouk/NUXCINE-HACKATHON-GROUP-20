import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import NotificationBell from '../../shared/components/NotificationBell';
import { listDriverOffers } from '../services/driverApi';
import { clearActiveOffer, setActiveOffer } from '../services/driverState';

export default function DashboardPage() {
  const navigate = useNavigate();
  const [available, setAvailable] = useState(false);
  const [offers, setOffers] = useState([]);
  const [loadingOffers, setLoadingOffers] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function loadOffers() {
      setLoadingOffers(true);
      setErrorMessage('');

      try {
        const response = await listDriverOffers();

        if (!isMounted) {
          return;
        }

        setOffers(response.offers);
      } catch (error) {
        if (isMounted) {
          setErrorMessage(error.message);
        }
      } finally {
        if (isMounted) {
          setLoadingOffers(false);
        }
      }
    }

    loadOffers();

    return () => {
      isMounted = false;
    };
  }, []);

  const openIncomingRequest = () => {
    const firstOffer = offers[0];

    if (!firstOffer) {
      clearActiveOffer();
      navigate('/driver/request');
      return;
    }

    setActiveOffer(firstOffer);
    navigate('/driver/request', { state: { offer: firstOffer } });
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Driver dashboard</h1>
        <NotificationBell />
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

      {loadingOffers ? <p>Loading offers...</p> : <p>Open offers: {offers.length}</p>}
      {errorMessage ? <p>{errorMessage}</p> : null}

      <button className="secondary-button" onClick={openIncomingRequest}>View incoming request</button>
    </main>
  );
}