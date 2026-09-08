import { useState } from 'react';
import { C, F } from './tokens';

import { SplashScreen, LoginScreen, SignupScreen, PrivacyScreen, TermsScreen } from './screens/auth';
import {
  PassengerHomeScreen, PassengerMapBookingScreen, PassengerConfirmScreen,
  PassengerSearchingScreen, PassengerDriverEnRouteScreen, PassengerRideInProgressScreen,
  PassengerRideCompletedScreen, PassengerHistoryScreen, PassengerProfileScreen,
  PassengerSupportScreen, PassengerNotificationsScreen,
} from './screens/passenger';
import {
  DriverDashboardScreen, DriverIncomingRequestScreen, DriverRideAcceptedScreen,
  DriverNavigationScreen, DriverRideInProgressScreen, DriverEndRideScreen,
  DriverEarningsScreen, DriverHistoryScreen, DriverProfileScreen, DriverSafetyScreen,
} from './screens/driver';
import {
  AdminDashboardScreen, AdminUsersScreen, AdminDriversScreen,
  AdminRidesScreen, AdminStatsScreen, AdminReportsScreen,
} from './screens/admin';

type ScreenType = 'mobile' | 'desktop';

type ScreenDef = {
  id: string;
  label: string;
  component: React.FC;
  type: ScreenType;
};

type Category = {
  id: string;
  label: string;
  emoji: string;
  screens: ScreenDef[];
};

const categories: Category[] = [
  {
    id: 'auth',
    label: 'Auth & Legal',
    emoji: '🔐',
    screens: [
      { id: 'splash',  label: 'Splash',          component: SplashScreen,  type: 'mobile' },
      { id: 'login',   label: 'Login',            component: LoginScreen,   type: 'mobile' },
      { id: 'signup',  label: 'Sign up',          component: SignupScreen,  type: 'mobile' },
      { id: 'privacy', label: 'Privacy Policy',   component: PrivacyScreen, type: 'mobile' },
      { id: 'terms',   label: 'Terms of Service', component: TermsScreen,   type: 'mobile' },
    ],
  },
  {
    id: 'passenger',
    label: 'Passenger',
    emoji: '🧍',
    screens: [
      { id: 'p-home',       label: 'Home',             component: PassengerHomeScreen,          type: 'mobile' },
      { id: 'p-map',        label: 'Map & Booking',    component: PassengerMapBookingScreen,    type: 'mobile' },
      { id: 'p-confirm',    label: 'Confirm ride',     component: PassengerConfirmScreen,       type: 'mobile' },
      { id: 'p-searching',  label: 'Searching',        component: PassengerSearchingScreen,     type: 'mobile' },
      { id: 'p-en-route',   label: 'Driver en route',  component: PassengerDriverEnRouteScreen, type: 'mobile' },
      { id: 'p-inprogress', label: 'Ride in progress', component: PassengerRideInProgressScreen,type: 'mobile' },
      { id: 'p-completed',  label: 'Ride completed',   component: PassengerRideCompletedScreen, type: 'mobile' },
      { id: 'p-history',    label: 'History',          component: PassengerHistoryScreen,       type: 'mobile' },
      { id: 'p-profile',    label: 'Profile',          component: PassengerProfileScreen,       type: 'mobile' },
      { id: 'p-support',    label: 'Support',          component: PassengerSupportScreen,       type: 'mobile' },
      { id: 'p-notifs',     label: 'Notifications',    component: PassengerNotificationsScreen, type: 'mobile' },
    ],
  },
  {
    id: 'driver',
    label: 'Driver',
    emoji: '🚗',
    screens: [
      { id: 'd-dashboard',  label: 'Dashboard',        component: DriverDashboardScreen,      type: 'mobile' },
      { id: 'd-incoming',   label: 'Incoming request', component: DriverIncomingRequestScreen, type: 'mobile' },
      { id: 'd-accepted',   label: 'Ride accepted',    component: DriverRideAcceptedScreen,   type: 'mobile' },
      { id: 'd-nav',        label: 'Navigation',       component: DriverNavigationScreen,     type: 'mobile' },
      { id: 'd-inprogress', label: 'Ride in progress', component: DriverRideInProgressScreen, type: 'mobile' },
      { id: 'd-endride',    label: 'End ride',         component: DriverEndRideScreen,        type: 'mobile' },
      { id: 'd-earnings',   label: 'Earnings',         component: DriverEarningsScreen,       type: 'mobile' },
      { id: 'd-history',    label: 'History',          component: DriverHistoryScreen,        type: 'mobile' },
      { id: 'd-profile',    label: 'Profile',          component: DriverProfileScreen,        type: 'mobile' },
      { id: 'd-safety',     label: 'Safety',           component: DriverSafetyScreen,         type: 'mobile' },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    emoji: '🛠',
    screens: [
      { id: 'a-dashboard', label: 'Dashboard', component: AdminDashboardScreen, type: 'desktop' },
      { id: 'a-users',     label: 'Users',     component: AdminUsersScreen,     type: 'desktop' },
      { id: 'a-drivers',   label: 'Drivers',   component: AdminDriversScreen,   type: 'desktop' },
      { id: 'a-rides',     label: 'Rides',     component: AdminRidesScreen,     type: 'desktop' },
      { id: 'a-stats',     label: 'Statistics',component: AdminStatsScreen,     type: 'desktop' },
      { id: 'a-reports',   label: 'Reports',   component: AdminReportsScreen,   type: 'desktop' },
    ],
  },
];

const allScreens = categories.flatMap(c => c.screens);

export default function App() {
  const [selectedId, setSelectedId] = useState('splash');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const selected = allScreens.find(s => s.id === selectedId) ?? allScreens[0];
  const SelectedComponent = selected.component;
  const selectedCat = categories.find(c => c.screens.some(s => s.id === selectedId));
  const isMobile = selected.type === 'mobile';

  const toggleCat = (id: string) =>
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: F.sans, overflow: 'hidden' }}>

      {/* ── Prototype sidebar ─────────────────────────────────────────────── */}
      <div style={{
        width: 252,
        backgroundColor: C.sidebar,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        flexShrink: 0,
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}>
        {/* Brand */}
        <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid rgba(255,255,255,0.08)', flexShrink: 0 }}>
          <div style={{ fontFamily: F.serif, fontSize: 22, color: '#fff', letterSpacing: '0.04em', marginBottom: 4 }}>VORA</div>
          <div style={{ fontFamily: F.sans, fontSize: 10, color: 'rgba(255,255,255,0.38)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Prototype · {allScreens.length} screens
          </div>
        </div>

        {/* Screen list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '10px 0 16px' }}>
          {categories.map(cat => {
            const open = !collapsed.has(cat.id);
            return (
              <div key={cat.id}>
                <button
                  onClick={() => toggleCat(cat.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '7px 16px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'rgba(255,255,255,0.45)',
                    fontFamily: F.sans,
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    textAlign: 'left',
                    marginTop: 6,
                  }}
                >
                  <span>{cat.emoji} {cat.label}</span>
                  <span style={{ fontSize: 9 }}>{open ? '▾' : '▸'}</span>
                </button>

                {open && cat.screens.map(screen => {
                  const active = screen.id === selectedId;
                  return (
                    <button
                      key={screen.id}
                      onClick={() => setSelectedId(screen.id)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 9,
                        padding: '7px 14px 7px 22px',
                        background: active ? `${C.primary}38` : 'none',
                        border: 'none',
                        borderLeft: active ? `2px solid ${C.primary}` : '2px solid transparent',
                        cursor: 'pointer',
                        fontFamily: F.sans,
                        fontSize: 13,
                        color: active ? '#fff' : 'rgba(255,255,255,0.55)',
                        fontWeight: active ? 700 : 400,
                        textAlign: 'left',
                        transition: 'color 0.1s, background 0.1s',
                      }}
                    >
                      {/* Device icon */}
                      <span style={{
                        display: 'inline-block',
                        flexShrink: 0,
                        width: screen.type === 'mobile' ? 7 : 12,
                        height: screen.type === 'mobile' ? 12 : 8,
                        borderRadius: screen.type === 'mobile' ? 2 : 1,
                        border: `1px solid ${active ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.2)'}`,
                      }} />
                      {screen.label}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 20px', borderTop: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
          <div style={{ fontFamily: F.sans, fontSize: 10, color: 'rgba(255,255,255,0.28)', lineHeight: 1.7 }}>
            VORA — NuxCine Hackathon 2026<br />
            Design system prototype
          </div>
        </div>
      </div>

      {/* ── Main view ─────────────────────────────────────────────────────── */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        backgroundColor: isMobile ? '#0b1610' : C.bg,
      }}>

        {/* Top bar */}
        <div style={{
          padding: '12px 24px',
          borderBottom: `1px solid ${isMobile ? 'rgba(255,255,255,0.07)' : C.border}`,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexShrink: 0,
          backgroundColor: isMobile ? '#0b1610' : C.surface,
        }}>
          <span style={{ fontFamily: F.sans, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: isMobile ? 'rgba(255,255,255,0.38)' : C.accent }}>
            {selectedCat?.emoji} {selectedCat?.label}
          </span>
          <span style={{ color: isMobile ? 'rgba(255,255,255,0.2)' : C.border }}>›</span>
          <span style={{ fontFamily: F.sans, fontSize: 13, fontWeight: 700, color: isMobile ? 'rgba(255,255,255,0.85)' : C.text }}>
            {selected.label}
          </span>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '3px 10px',
              borderRadius: 999,
              backgroundColor: isMobile ? 'rgba(255,255,255,0.07)' : C.muted,
              border: `1px solid ${isMobile ? 'rgba(255,255,255,0.12)' : C.border}`,
              fontFamily: F.sans,
              fontSize: 10,
              fontWeight: 700,
              color: isMobile ? 'rgba(255,255,255,0.5)' : C.accent,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}>
              {isMobile ? '📱 390 × 844' : '🖥 Desktop'}
            </span>
          </div>
        </div>

        {/* Screen view */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          alignItems: isMobile ? 'center' : 'flex-start',
          justifyContent: isMobile ? 'center' : 'flex-start',
          padding: isMobile ? '36px 24px' : 0,
        }}>
          {isMobile ? (
            /* Phone frame */
            <div style={{
              width: 414,
              height: 868,
              backgroundColor: '#080e0b',
              borderRadius: 52,
              padding: 12,
              boxShadow: '0 64px 128px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.04)',
              position: 'relative',
              flexShrink: 0,
            }}>
              {/* Dynamic island */}
              <div style={{
                position: 'absolute',
                top: 18,
                left: '50%',
                transform: 'translateX(-50%)',
                width: 128,
                height: 37,
                backgroundColor: '#000',
                borderRadius: 22,
                zIndex: 20,
              }} />
              {/* Side button */}
              <div style={{ position: 'absolute', right: -3, top: 116, width: 3, height: 64, backgroundColor: '#1e1e1e', borderRadius: '0 2px 2px 0' }} />
              {/* Volume buttons */}
              <div style={{ position: 'absolute', left: -3, top: 100, width: 3, height: 36, backgroundColor: '#1e1e1e', borderRadius: '2px 0 0 2px' }} />
              <div style={{ position: 'absolute', left: -3, top: 148, width: 3, height: 36, backgroundColor: '#1e1e1e', borderRadius: '2px 0 0 2px' }} />

              {/* Screen */}
              <div style={{ width: '100%', height: '100%', borderRadius: 40, overflow: 'hidden', position: 'relative' }}>
                {/* Status bar */}
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 54,
                  zIndex: 15,
                  pointerEvents: 'none',
                  display: 'flex',
                  alignItems: 'flex-start',
                  padding: '14px 28px 0',
                  justifyContent: 'space-between',
                }}>
                  <span style={{ fontFamily: F.sans, fontSize: 13, fontWeight: 700, color: C.text, mixBlendMode: 'multiply' }}>9:41</span>
                  <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: C.text, mixBlendMode: 'multiply' }}>●●●● WiFi 🔋</span>
                  </div>
                </div>

                {/* Screen content */}
                <div style={{ position: 'absolute', inset: 0 }}>
                  <SelectedComponent />
                </div>
              </div>
            </div>
          ) : (
            /* Desktop admin view */
            <div style={{ width: '100%', height: '100%', overflow: 'auto' }}>
              <SelectedComponent />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
