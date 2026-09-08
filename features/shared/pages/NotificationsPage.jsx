import { useNotifications } from '../context/NotificationContext';
import PageHeader from '../components/PageHeader';
import Icon from '../components/Icon';
import { getLocale } from '../services/locale';

export default function NotificationsPage() {
  const { notifications } = useNotifications();
  const en = getLocale() === 'en';

  const when = (at) => {
    if (!at) return '';
    return new Date(at).toLocaleString(en ? 'en-GB' : 'fr-FR', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <main className="app-shell">
      <PageHeader
        title={en ? 'Notifications' : 'Notifications'}
        fallback="/passenger/home"
      />

      {notifications.length === 0 ? (
        <div className="empty-state">
          <Icon name="clock" size={26} />
          <p>
            {en
              ? 'Nothing yet. Updates about your trips appear here.'
              : 'Rien pour le moment. Les mises a jour de vos trajets apparaitront ici.'}
          </p>
        </div>
      ) : (
        <ul className="recent-list">
          {notifications.map((n) => (
            <li key={n.id}>
              <button type="button" disabled>
                <span className="recent-list__body">
                  <span className="recent-list__label">{n.title}</span>
                  <span className="recent-list__fare">{n.body}</span>
                  <span className="recent-list__fare">{when(n.at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Said rather than implied by an empty list. */}
      <p className="section-note">
        {en
          ? 'These are built from your own trips. There is no push channel yet, so nothing arrives while the app is closed.'
          : "Ces elements sont construits a partir de vos propres trajets. Il n'y a pas encore de canal de notification poussee, donc rien n'arrive quand l'application est fermee."}
      </p>
    </main>
  );
}
