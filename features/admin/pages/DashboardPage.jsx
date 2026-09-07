export default function DashboardPage() {
  const stats = [
    { label: 'Active rides', value: 3 },
    { label: 'Online drivers', value: 7 },
    { label: 'Total users', value: 142 },
  ];

  return (
    <main className="app-shell">
      <h1>Admin overview</h1>
      <div className="stats-grid">
        {stats.map((s) => (
          <div key={s.label} className="stat-card">
            <p className="stat-value">{s.value}</p>
            <p className="stat-label">{s.label}</p>
          </div>
        ))}
      </div>
    </main>
  );
}