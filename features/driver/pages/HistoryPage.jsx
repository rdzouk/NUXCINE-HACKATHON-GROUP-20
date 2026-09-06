import { useMockAuth } from '../../../app/MockAuthContext';
import DriverNav from '../components/DriverNav';

export default function HistoryPage() {
  const { rideHistory } = useMockAuth();

  return (
    <main className="app-shell">
      <h1>Ride history</h1>
      <ul className="history-list">
        {rideHistory.map((r) => (
          <li key={r.id}><p>{r.from} → {r.to}</p><p>{r.date}</p></li>
        ))}
      </ul>
      <DriverNav />
    </main>
  );
}