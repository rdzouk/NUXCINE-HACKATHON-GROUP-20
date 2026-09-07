import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { acceptDriverOffer, declineDriverOffer, listDriverOffers } from '../services/driverApi';
import {
  clearActiveDriverRide,
  clearActiveOffer,
  getActiveOffer,
  setActiveDriverRide,
  setActiveOffer,
} from '../services/driverState';

export default function IncomingRequestPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [offer, setOffer] = useState(() => location.state?.offer ?? getActiveOffer());
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [hintMessage, setHintMessage] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function loadOffers() {
      if (offer) {
        return;
      }

      setIsLoading(true);
      setErrorMessage('');

      try {
        const response = await listDriverOffers();

        if (!isMounted) {
          return;
        }

        const nextOffer = response.offers[0] ?? null;
        setOffer(nextOffer);

        if (nextOffer) {
          setActiveOffer(nextOffer);
        } else {
          clearActiveOffer();
        }
      } catch (error) {
        if (isMounted) {
          setErrorMessage(error.message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadOffers();

    return () => {
      isMounted = false;
    };
  }, [offer]);

  const tripSummary = useMemo(() => {
    if (!offer) {
      return null;
    }

    return {
      pickup: offer.pickup.label,
      dropoff: offer.dropoff.label,
      fareXaf: offer.fare_xaf,
      distanceKm: offer.trip_distance_m / 1000,
      durationMin: Math.round(offer.trip_duration_s / 60),
      seats: offer.seats,
    };
  }, [offer]);

  const handleDecline = async () => {
    if (!offer) {
      navigate('/driver/dashboard');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');

    try {
      await declineDriverOffer(offer.id);
      clearActiveOffer();
      clearActiveDriverRide();
      navigate('/driver/dashboard', { replace: true });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!offer) {
      return;
    }

    setIsLoading(true);
    setErrorMessage('');
    setHintMessage('');

    try {
      const response = await acceptDriverOffer(offer.id);
      setActiveDriverRide(response.ride);
      clearActiveOffer();
      navigate('/driver/accepted', { state: { ride: response.ride }, replace: true });
    } catch (error) {
      setErrorMessage(error.message);

      if (error.code === 'OFFER_TAKEN') {
        setHintMessage('This offer was already taken. Refresh offers to get the next one.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-shell centered">
      <h2>New ride request</h2>

      {isLoading && !tripSummary ? <p>Loading offers...</p> : null}

      {tripSummary ? (
        <>
          <div className="ride-summary">
            <p><strong>Pickup:</strong> {tripSummary.pickup}</p>
            <p><strong>Drop-off:</strong> {tripSummary.dropoff}</p>
            <p><strong>Trip:</strong> {tripSummary.distanceKm.toFixed(1)} km, {tripSummary.durationMin} min</p>
            <p><strong>Seats:</strong> {tripSummary.seats}</p>
            <p><strong>Fare:</strong> {tripSummary.fareXaf.toLocaleString()} FCFA</p>
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={handleDecline} disabled={isLoading}>Decline</button>
            <button className="primary-button" onClick={handleAccept} disabled={isLoading}>Accept</button>
          </div>
        </>
      ) : (
        <p>No open offers right now.</p>
      )}

      {errorMessage ? <p>{errorMessage}</p> : null}
      {hintMessage ? <p>{hintMessage}</p> : null}
    </main>
  );
}