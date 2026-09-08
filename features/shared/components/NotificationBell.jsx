import { Link } from 'react-router-dom';
import { useNotifications } from '../context/NotificationContext';
import Icon from './Icon';

/**
 * Unread count, in the app's own typeface and colour.
 *
 * The bell was an emoji, which renders in a different style on every platform,
 * ignores `currentColor`, and sits wherever the system font puts it. This is
 * the same outlined set as the rest of the interface.
 */
export default function NotificationBell() {
  const { unreadCount } = useNotifications();

  return (
    <Link
      to="/notifications"
      className="notification-bell"
      aria-label={
        unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'
      }
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 8a6 6 0 1 0-12 0c0 6-2 7-2 7h16s-2-1-2-7" />
        <path d="M10.5 19a1.8 1.8 0 0 0 3 0" />
      </svg>
      {unreadCount > 0 ? (
        <span className="notification-badge">{unreadCount}</span>
      ) : null}
    </Link>
  );
}
