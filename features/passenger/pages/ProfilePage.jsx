import { useMockAuth } from '../../../app/MockAuthContext';
import BottomNav from '../components/BottomNav';

export default function ProfilePage() {
  const { user } = useMockAuth();

  return (
    <main className="app-shell">
      <h1>Profile</h1>
      <p><strong>Name:</strong> {user.name}</p>
      <p><strong>Phone:</strong> {user.phone}</p>
      <p><strong>Rating:</strong> ⭐ {user.rating}</p>
      <button className="secondary-button">Edit profile</button>
      <button className="secondary-button">Log out</button>
      <BottomNav />
    </main>
  );
}