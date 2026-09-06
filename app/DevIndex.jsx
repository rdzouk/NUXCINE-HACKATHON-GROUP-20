import { Link } from 'react-router-dom';

const screens = [
  ['Auth', [['Splash', '/splash'], ['Login', '/login'], ['Signup', '/signup']]],
  ['Passenger', [['Home', '/passenger/home'], ['Book', '/passenger/book'], ['History', '/passenger/history'], ['Profile', '/passenger/profile'], ['Support', '/passenger/support']]],
  ['Driver', [['Dashboard', '/driver/dashboard'], ['Incoming request', '/driver/request']]],
  ['Admin', [['Dashboard', '/admin/dashboard']]],
];

export default function DevIndex() {
  return (
    <main>
      <h1>VORA screen hub</h1>
      {screens.map(([group, links]) => (
        <section key={group}>
          <h2>{group}</h2>
          {links.map(([label, path]) => <Link key={path} to={path}>{label}</Link>)}
        </section>
      ))}
    </main>
  );
}
