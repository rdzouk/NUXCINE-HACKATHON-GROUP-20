import { useMockAuth } from '../../shared/context/MockAuthContext';
import Sidebar from '../components/Sidebar';

export default function UsersPage() {
  const { adminUsers } = useMockAuth();

  return (
    <div className="admin-layout">
      <Sidebar />
      <main className="app-shell">
        <h1>Users</h1>
        <table className="admin-table">
          <thead><tr><th>Name</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {adminUsers.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td><td>{u.role}</td><td>{u.status}</td>
                <td><button className="secondary-button">
                  {u.status === 'active' ? 'Suspend' : 'Activate'}
                </button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}