import { useMockAuth } from '../../shared/context/MockAuthContext';
import Sidebar from '../components/Sidebar';

export default function StatsPage() {
  const { adminRides, adminDrivers, adminUsers } = useMockAuth();
  const stats = [
    { label: 'Total rides', value: adminRides.length },
    { label: 'Online drivers', value: adminDrivers.filter((d) => d.status === 'online').length },
    { label: 'Total users', value: adminUsers.length },
  ];

  return (
    <div className="admin-layout">
      <Sidebar />
      <main className="app-shell">
        <h1>Statistics</h1>
        <div className="stats-grid">
          {stats.map((s) => (
            <div key={s.label} className="stat-card">
              <p className="stat-value">{s.value}</p>
              <p className="stat-label">{s.label}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}