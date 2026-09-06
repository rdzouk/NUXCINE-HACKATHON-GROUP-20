import { Link, useLocation } from 'react-router-dom';

const tabs = [
  ['Home', '/passenger/home'],
  ['History', '/passenger/history'],
  ['Profile', '/passenger/profile'],
];

export default function BottomNav() {
  const { pathname } = useLocation();
  return (
    <nav className="bottom-nav">
      {tabs.map(([label, path]) => (
        <Link key={path} to={path} className={pathname === path ? 'active' : ''}>
          {label}
        </Link>
      ))}
    </nav>
  );
}