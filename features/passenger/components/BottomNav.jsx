import { Link, useLocation } from 'react-router-dom';
import { t } from '../../shared/services/strings';

// The keys, not the labels. `t` was imported and never called, so the tab bar
// stayed in English under a French interface: the one strip of chrome visible
// on every screen was the one thing that never translated.
const TABS = [
  ['common.home', '/passenger/home'],
  ['common.history', '/passenger/history'],
  ['common.profile', '/passenger/profile'],
];

export default function BottomNav() {
  const { pathname } = useLocation();

  return (
    <nav className="bottom-nav">
      {TABS.map(([key, path]) => (
        <Link key={path} to={path} className={pathname === path ? 'active' : ''}>
          {t(key)}
        </Link>
      ))}
    </nav>
  );
}
