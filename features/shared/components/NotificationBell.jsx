import { Link } from 'react-router-dom';
import { useNotifications } from '../../../app/NotificationContext';

export default function NotificationBell() {
  const { unreadCount } = useNotifications();
  return (
    <Link to="/notifications" className="notification-bell">
      🔔
      {unreadCount > 0 && <span className="notification-badge">{unreadCount}</span>}
    </Link>
  );
}