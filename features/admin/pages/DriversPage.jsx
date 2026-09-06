import { useMockAuth } from '../../../app/MockAuthContext';
import Sidebar from '../components/Sidebar';

export default function DriversPage() {
  const { adminDrivers } = useMockAuth();

  return (
    <div className="admin-layout">
      <Sidebar />
      <main className="app-shell">
        <h1>Drivers</h1>
        <table className="admin-table">
          <thead><tr><th>Name</th><th>Vehicle</th><th>Status</th></tr></thead>
          <tbody>
            {adminDrivers.map((d) => (
              <tr key={d.id}><td>{d.name}</td><td>{d.vehicle}</td><td>{d.status}</td></tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}