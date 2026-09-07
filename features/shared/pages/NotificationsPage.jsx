import { useNotifications } from '../../../app/NotificationContext';

export default function NotificationsPage() {
  const { notifications } = useNotifications();

  return (
    <main className="app-shell">
      <h1>Notifications</h1>
      {notifications.length === 0 ? (
        <p>No notifications yet.</p>
      ) : (
        <ul className="history-list">
          {notifications.map((n) => (
            <li key={n.id} style={{ opacity: n.read ? 0.6 : 1 }}>
              <p><strong>{n.title}</strong></p>
              <p>{n.body}</p>
              <p className="eyebrow">{n.time}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}