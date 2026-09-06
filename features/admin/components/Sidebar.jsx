import { Link, useLocation } from 'react-router-dom';

const items = [
  ['Dashboard', '/admin/dashboard'],
  ['Users', '/admin/users'],
  ['Drivers', '/admin/drivers'],
  ['Rides', '/admin/rides'],
  ['Stats', '/admin/stats'],
  ['Reports', '/admin/reports'],
];

export default function Sidebar() {
  const { pathname } = useLocation();
  return (
    <aside className="admin-sidebar">
      <h2>VORA Admin</h2>
      {items.map(([label, path]) => (
        <Link key={path} to={path} className={pathname === path ? 'active' : ''}>{label}</Link>
      ))}
    </aside>
  );
}