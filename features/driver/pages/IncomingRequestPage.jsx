import { useNavigate } from 'react-router-dom';

export default function IncomingRequestPage() {
  const navigate = useNavigate();

  return (
    <main className="app-shell centered">
      <h2>New ride request</h2>
      <div className="ride-summary">
        <p><strong>Passenger:</strong> Aminata · ⭐ 4.8</p>
        <p><strong>Pickup:</strong> Carrefour Warda</p>
        <p><strong>Drop-off:</strong> Total Nsimeyong</p>
        <p><strong>Fare:</strong> 1,800 FCFA</p>
      </div>
      <div className="button-row">
        <button className="secondary-button" onClick={() => navigate('/driver/dashboard')}>Decline</button>
        <button className="primary-button" onClick={() => navigate('/driver/accepted')}>Accept</button>
      </div>
    </main>
  );
}