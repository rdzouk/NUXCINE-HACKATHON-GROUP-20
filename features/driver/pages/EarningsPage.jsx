import { useMockAuth } from '../../../app/MockAuthContext';
import DriverNav from '../components/DriverNav';

export default function EarningsPage() {
  const { rideHistory } = useMockAuth();
  const total = rideHistory.reduce((sum, r) => sum + r.fareXaf, 0);

  return (
    <main className="app-shell">
      <h1>Earnings</h1>
      <div className="stat-card">
        <p className="stat-value">{total.toLocaleString()} FCFA</p>
        <p className="stat-label">This week</p>
      </div>
      <ul className="history-list">
        {rideHistory.map((r) => (
          <li key={r.id}><p>{r.date}</p><p>{r.fareXaf.toLocaleString()} FCFA</p></li>
        ))}
      </ul>
      <DriverNav />
    </main>
  );
}