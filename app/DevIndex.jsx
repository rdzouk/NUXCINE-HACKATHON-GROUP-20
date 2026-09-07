import { Link } from 'react-router-dom';

const links = [
  { section: 'Auth', pages: [['Splash', '/splash'], ['Login', '/login'], ['Signup', '/signup']] },
  { section: 'Passenger', pages: [
    ['Home', '/passenger/home'], ['Book a ride', '/passenger/book'], ['Confirm', '/passenger/confirm'],
    ['Searching driver', '/passenger/searching'], ['Driver en route', '/passenger/driver-enroute'],
    ['Ride in progress', '/passenger/ride'],
    ['Ride completed', '/passenger/completed'], ['History', '/passenger/history'],
    ['Profile', '/passenger/profile'], ['Support', '/passenger/support'], ['Notifications', '/notifications'],
    ['Privacy policy', '/legal/privacy'], ['Terms', '/legal/terms'],
  ]},
  { section: 'Driver', pages: [
    ['Dashboard', '/driver/dashboard'], ['Incoming request', '/driver/request'],
    ['Ride accepted', '/driver/accepted'], ['Navigation', '/driver/navigate'],
    ['Ride in progress', '/driver/ride'], ['End ride', '/driver/end'],
    ['Earnings', '/driver/earnings'], ['History', '/driver/history'],
    ['Profile', '/driver/profile'], ['Safety', '/driver/safety'],
  ]},
  { section: 'Admin', pages: [
    ['Dashboard', '/admin/dashboard'], ['Users', '/admin/users'], ['Drivers', '/admin/drivers'],
    ['Rides', '/admin/rides'], ['Stats', '/admin/stats'], ['Reports', '/admin/reports'],
  ]},
];

export default function DevIndex() {
  return (
    <div style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>VORA — screen index (dev only)</h1>
      {links.map(({ section, pages }) => (
        <div key={section}>
          <h3>{section}</h3>
          <ul>
            {pages.map(([label, path]) => (
              <li key={path}><Link to={path}>{label}</Link></li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}