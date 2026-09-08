import { useMockAuth } from '../../shared/context/MockAuthContext';
import Sidebar from '../components/Sidebar';

export default function ReportsPage() {
  const { adminReports } = useMockAuth();

  return (
    <div className="admin-layout">
      <Sidebar />
      <main className="app-shell">
        <h1>Reports & incidents</h1>
        <ul className="history-list">
          {adminReports.map((r) => (
            <li key={r.id}>
              <p><strong>{r.type}</strong> — Ride #{r.ride}</p>
              <p>{r.note}</p>
              <p>Status: {r.status}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}