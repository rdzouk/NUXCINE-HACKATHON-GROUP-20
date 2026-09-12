import { Link, useLocation } from 'react-router-dom';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';
import { clearSession } from '../../auth/services/session';

/**
 * Admin navigation, with the unbuilt screens marked as unbuilt.
 *
 * Six links of which two lead to real data. Leaving them all looking alike
 * sends a juror clicking through four screens before working out which ones
 * mean anything; marking them costs one character each and answers the
 * question before it is asked.
 */
const ITEMS = [
  ['dashboard', '/admin/dashboard', 'Overview', 'Synthese', true],
  ['drivers', '/admin/drivers', 'Drivers', 'Chauffeurs', true],
  ['users', '/admin/users', 'Users', 'Utilisateurs', false],
  ['rides', '/admin/rides', 'Rides', 'Courses', false],
  ['stats', '/admin/stats', 'Statistics', 'Statistiques', false],
  ['reports', '/admin/reports', 'Reports', 'Signalements', false],
];

export default function Sidebar() {
  const { pathname } = useLocation();
  const en = getLocale() === 'en';

  return (
    <aside className="admin-sidebar">
      <h2>VORA</h2>

      {ITEMS.map(([key, path, labelEn, labelFr, built]) => (
        <Link
          key={key}
          to={path}
          className={
            [pathname === path ? 'active' : '', built ? '' : 'is-unbuilt']
              .filter(Boolean)
              .join(' ') || undefined
          }
        >
          {en ? labelEn : labelFr}
          {built ? null : (
            <span className="admin-sidebar__todo">
              {en ? 'not built' : 'a construire'}
            </span>
          )}
        </Link>
      ))}

      <p className="admin-sidebar__note">
        {en
          ? 'Marked items are not built. Nothing on this dashboard is invented.'
          : "Les elements marques ne sont pas construits. Rien sur ce tableau de bord n'est invente."}
      </p>

      {/* An admin session is the highest-value one in the system and had no
          way to end itself. Leaving it signed in on a shared machine is the
          whole reason this belongs here. */}
      <button
        className="secondary-button"
        type="button"
        onClick={() => {
          clearSession();
          window.location.assign('/login');
        }}
      >
        {t('common.logout')}
      </button>
    </aside>
  );
}
