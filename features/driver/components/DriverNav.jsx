import { Link, useLocation } from 'react-router-dom';
import { getLocale } from '../../shared/services/locale';

const TABS = [
  ['/driver/dashboard', 'Dashboard', 'Tableau de bord'],
  ['/driver/earnings', 'Earnings', 'Gains'],
  ['/driver/history', 'History', 'Historique'],
  ['/driver/profile', 'Profile', 'Profil'],
];

export default function DriverNav() {
  const { pathname } = useLocation();
  const en = getLocale() === 'en';

  return (
    <nav className="bottom-nav">
      {TABS.map(([path, labelEn, labelFr]) => (
        <Link key={path} to={path} className={pathname === path ? 'active' : ''}>
          {en ? labelEn : labelFr}
        </Link>
      ))}
    </nav>
  );
}
