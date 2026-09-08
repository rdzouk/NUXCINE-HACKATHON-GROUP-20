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
import RideInstructions from '../components/RideInstructions';
import { getLocale } from '../../shared/services/locale';

export default function IncomingRequestPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const en = getLocale() === 'en';
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
        setHintMessage(
          en
            ? 'Another driver took this one. Go back for the next offer.'
            : 'Un autre chauffeur a pris cette course. Revenez pour la suivante.',
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <p className="eyebrow">{en ? 'Incoming' : 'Demande entrante'}</p>
      <h1 className="headline">
        {en ? 'New ride request' : 'Nouvelle course'}
      </h1>

      {isLoading && !tripSummary ? (
        <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
      ) : null}

      {tripSummary ? (
        <>
          <p className="eta-block">
            {tripSummary.fareXaf.toLocaleString()} FCFA
          </p>

          <div className="fact-row">
            <span>{en ? 'Pick up' : 'Depart'}</span>
            <strong>{tripSummary.pickup}</strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'Drop off' : 'Arrivee'}</span>
            <strong>{tripSummary.dropoff}</strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'Trip' : 'Trajet'}</span>
            <strong>
              {tripSummary.distanceKm.toFixed(1)} km, {tripSummary.durationMin} min
            </strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'Seats' : 'Places'}</span>
            <strong>{tripSummary.seats}</strong>
          </div>

          {/* Before the decision, not after it. A driver who accepts and only
              then learns what was asked of them has agreed to something they
              did not read. */}
          <RideInstructions ride={offer} />

          <div className="button-row">
            <button
              className="secondary-button"
              onClick={handleDecline}
              disabled={isLoading}
            >
              {en ? 'Decline' : 'Refuser'}
            </button>
            <button
              className="primary-button"
              onClick={handleAccept}
              disabled={isLoading}
            >
              {en ? 'Accept' : 'Accepter'}
            </button>
          </div>
        </>
      ) : (
        <p className="section-note">
          {en ? 'No open offers right now.' : 'Aucune demande en attente.'}
        </p>
      )}

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {hintMessage ? <p className="section-note">{hintMessage}</p> : null}
    </main>
  );
}