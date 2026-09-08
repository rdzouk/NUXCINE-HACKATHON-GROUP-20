import { useLocation, useNavigate } from 'react-router-dom';
import { clearActiveDriverRide, clearCompletedDriverRide, getCompletedDriverRide } from '../services/driverState';
import { getLocale } from '../../shared/services/locale';

export default function EndRidePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const completion = getCompletedDriverRide();
  const en = getLocale() === 'en';
  const finalFareXaf = location.state?.finalFareXaf ?? completion?.finalFareXaf ?? completion?.ride?.final_fare_xaf ?? null;

  const handleBack = () => {
    clearCompletedDriverRide();
    clearActiveDriverRide();
    navigate('/driver/dashboard');
  };

  return (
    <main className="app-shell centered">
      <h1 className="headline">
        {en ? 'Trip complete' : 'Course terminee'}
      </h1>
      <p className="eta-block">
        {typeof finalFareXaf === 'number'
          ? `${finalFareXaf.toLocaleString()} FCFA`
          : '-'}
      </p>
      <p className="section-note">
        {en
          ? 'Collect this in cash. The server computed it from its own record of the route.'
          : 'A percevoir en especes. Le montant a ete calcule par le serveur a partir de son propre releve du trajet.'}
      </p>
      <button className="primary-button" onClick={handleBack}>
        {en ? 'Back to the dashboard' : 'Retour au tableau de bord'}
      </button>
    </main>
  );
}