import { useMockAuth } from '../../../app/MockAuthContext';
import Sidebar from '../components/Sidebar';

export default function RidesPage() {
  const { adminRides } = useMockAuth();

  return (
    <div className="admin-layout">
      <Sidebar />
      <main className="app-shell">
        <h1>Rides</h1>
        <table className="admin-table">
          <thead><tr><th>ID</th><th>Passenger</th><th>Driver</th><th>Status</th><th>Fare</th></tr></thead>
          <tbody>
            {adminRides.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td><td>{r.passenger}</td><td>{r.driver}</td>
                <td>{r.status}</td><td>{r.fareXaf.toLocaleString()} FCFA</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}