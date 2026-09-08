import DriverNav from '../components/DriverNav';
import PageHeader from '../../shared/components/PageHeader';

export default function ProfilePage() {
  return (
    <main className="app-shell">
      <PageHeader title="Profile" fallback="/driver/dashboard" />
      <p><strong>Name:</strong> Jean</p>
      <p><strong>Vehicle:</strong> Toyota Corolla, gris, LT 1234 AB</p>
      <p><strong>Rating:</strong> ⭐ 4.9</p>
      <button className="secondary-button">Edit profile</button>
      <DriverNav />
    </main>
  );
}