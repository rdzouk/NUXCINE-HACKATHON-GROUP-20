import { Link, useLocation } from 'react-router-dom';

const tabs = [
  ['Dashboard', '/driver/dashboard'],
  ['Earnings', '/driver/earnings'],
  ['History', '/driver/history'],
  ['Profile', '/driver/profile'],
];

export default function DriverNav() {
  const { pathname } = useLocation();
  return (
    <nav className="bottom-nav">
      {tabs.map(([label, path]) => (
        <Link key={path} to={path} className={pathname === path ? 'active' : ''}>{label}</Link>
      ))}
    </nav>
  );
}