import { C, F } from '../tokens';
import { AdminSidebar, SmallLabel, StatCard, H1, H3, StatusBadge } from '../ui';

function AdminShell({ active, children }: { active: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', height: '100%', backgroundColor: C.bg, fontFamily: F.sans }}>
      <AdminSidebar active={active} />
      <div style={{ flex: 1, overflow: 'auto', padding: '36px 40px' }}>
        {children}
      </div>
    </div>
  );
}

function AdminTable({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div style={{ backgroundColor: C.surface, borderRadius: 10, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ backgroundColor: C.muted, borderBottom: `1px solid ${C.border}` }}>
            {headers.map(h => (
              <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontFamily: F.sans, fontSize: 12, fontWeight: 700, color: C.accent, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${C.border}` : 'none' }}>
              {row.map((cell, j) => (
                <td key={j} style={{ padding: '14px 16px', fontFamily: F.sans, fontSize: 14, color: C.text }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionLink({ children }: { children: React.ReactNode }) {
  return (
    <button style={{ fontFamily: F.sans, fontSize: 13, color: C.primary, fontWeight: 700, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
      {children} →
    </button>
  );
}

function bold(s: string) {
  return <strong style={{ fontWeight: 700, color: C.text }}>{s}</strong>;
}

function muted(s: string) {
  return <span style={{ color: C.accent }}>{s}</span>;
}

export function AdminDashboardScreen() {
  return (
    <AdminShell active="dashboard">
      <H1>Dashboard</H1>

      <div style={{ display: 'flex', gap: 20, marginBottom: 40 }}>
        <StatCard value="24" label="Active rides" />
        <StatCard value="87" label="Online drivers" />
        <StatCard value="3 241" label="Total users" />
      </div>

      <H3>Recent activity</H3>
      <div style={{ marginTop: 12 }}>
        <AdminTable
          headers={['Ride ID', 'Passenger', 'Driver', 'Status', 'Fare']}
          rows={[
            ['#VR-2091', bold('Aminata B.'), 'Koffi M.', <StatusBadge type="available">In progress</StatusBadge>, bold('1 200 XAF')],
            ['#VR-2090', bold('Jean K.'), 'Paul A.', <StatusBadge type="neutral">Completed</StatusBadge>, bold('3 500 XAF')],
            ['#VR-2089', bold('Marie F.'), 'Samuel N.', <StatusBadge type="neutral">Completed</StatusBadge>, bold('900 XAF')],
            ['#VR-2088', bold('Pierre N.'), 'Koffi M.', <StatusBadge type="offline">Cancelled</StatusBadge>, muted('—')],
          ]}
        />
      </div>
    </AdminShell>
  );
}

export function AdminUsersScreen() {
  return (
    <AdminShell active="users">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <H1 style={{ margin: 0 }}>Users</H1>
        <button style={{ backgroundColor: C.primary, color: '#fff', fontFamily: F.sans, fontSize: 14, fontWeight: 700, padding: '10px 18px', borderRadius: 8, border: 'none', cursor: 'pointer' }}>
          + Add user
        </button>
      </div>

      <AdminTable
        headers={['Name', 'Role', 'Joined', 'Status', 'Action']}
        rows={[
          [bold('Aminata Bello'), muted('Passenger'), muted('12 Mar 2025'), <StatusBadge type="available">Active</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Jean Kanga'), muted('Passenger'), muted('4 Apr 2025'), <StatusBadge type="available">Active</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Marie Fonkam'), muted('Passenger'), muted('18 Jan 2025'), <StatusBadge type="offline">Suspended</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Pierre Nkoulou'), muted('Passenger'), muted('2 Jun 2025'), <StatusBadge type="available">Active</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Cecile Mbarga'), muted('Passenger'), muted('30 Jul 2025'), <StatusBadge type="available">Active</StatusBadge>, <ActionLink>View</ActionLink>],
        ]}
      />
    </AdminShell>
  );
}

export function AdminDriversScreen() {
  return (
    <AdminShell active="drivers">
      <H1>Drivers</H1>

      <AdminTable
        headers={['Name', 'Vehicle', 'Rating', 'Status', 'Action']}
        rows={[
          [bold('Koffi Mensah'), muted('Toyota Corolla · CM 4521 AD'), '⭐ 4.9', <StatusBadge type="available">Online</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Paul Abomo'), muted('Honda Civic · CE 8831 LT'), '⭐ 4.7', <StatusBadge type="available">Online</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Samuel Nkeng'), muted('Hyundai i20 · LT 2201 DL'), '⭐ 4.5', <StatusBadge type="offline">Offline</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Eric Mvondo'), muted('Toyota Vitz · SW 9912 AB'), '⭐ 4.8', <StatusBadge type="available">Online</StatusBadge>, <ActionLink>View</ActionLink>],
          [bold('Alain Tabi'), muted('Nissan Sentra · AD 5502 MN'), '⭐ 3.9', <StatusBadge type="offline">Suspended</StatusBadge>, <ActionLink>View</ActionLink>],
        ]}
      />
    </AdminShell>
  );
}

export function AdminRidesScreen() {
  return (
    <AdminShell active="rides">
      <H1>Rides</H1>

      <AdminTable
        headers={['ID', 'Passenger', 'Driver', 'Status', 'Fare']}
        rows={[
          [muted('#VR-2091'), bold('Aminata B.'), 'Koffi M.', <StatusBadge type="available">In progress</StatusBadge>, bold('1 200 XAF')],
          [muted('#VR-2090'), bold('Jean K.'), 'Paul A.', <StatusBadge type="neutral">Completed</StatusBadge>, bold('3 500 XAF')],
          [muted('#VR-2089'), bold('Marie F.'), 'Samuel N.', <StatusBadge type="neutral">Completed</StatusBadge>, bold('900 XAF')],
          [muted('#VR-2088'), bold('Pierre N.'), 'Koffi M.', <StatusBadge type="offline">Cancelled</StatusBadge>, muted('—')],
          [muted('#VR-2087'), bold('Cecile M.'), 'Eric M.', <StatusBadge type="neutral">Completed</StatusBadge>, bold('1 800 XAF')],
        ]}
      />
    </AdminShell>
  );
}

export function AdminStatsScreen() {
  return (
    <AdminShell active="stats">
      <H1>Statistics</H1>

      <div style={{ display: 'flex', gap: 20, marginBottom: 36 }}>
        <StatCard value="312" label="Rides this month" />
        <StatCard value="174 500" label="XAF platform revenue" />
        <StatCard value="4.8" label="Average rating" />
      </div>

      <H3>Weekly breakdown</H3>
      <div style={{ marginTop: 12 }}>
        <AdminTable
          headers={['Week', 'Rides', 'Revenue (XAF)', 'New users', 'Avg rating']}
          rows={[
            [bold('Sep 1–7'), '98', <span style={{ color: C.primary, fontWeight: 700 }}>58 200</span>, '12', '⭐ 4.9'],
            [bold('Aug 25–31'), '81', <span style={{ color: C.primary, fontWeight: 700 }}>47 300</span>, '8', '⭐ 4.8'],
            [bold('Aug 18–24'), '74', <span style={{ color: C.primary, fontWeight: 700 }}>42 100</span>, '15', '⭐ 4.7'],
            [bold('Aug 11–17'), '59', <span style={{ color: C.primary, fontWeight: 700 }}>26 900</span>, '6', '⭐ 4.8'],
          ]}
        />
      </div>
    </AdminShell>
  );
}

export function AdminReportsScreen() {
  const reports = [
    { type: 'Unsafe driving', ref: '#VR-2085', note: 'Passenger reports driver ran two red lights on Boulevard de la Réunification.', status: 'Under review' },
    { type: 'Payment dispute', ref: '#VR-2079', note: 'Fare charged was significantly higher than the in-app estimate.', status: 'Resolved' },
    { type: 'Vehicle condition', ref: '#VR-2071', note: 'Air conditioning was not functioning during a 45-minute trip.', status: 'Closed' },
    { type: 'Abusive behavior', ref: '#VR-2065', note: 'Driver was verbally aggressive during a pickup location dispute.', status: 'Under review' },
    { type: 'No-show', ref: '#VR-2058', note: 'Driver accepted then did not arrive; did not respond to calls or messages.', status: 'Resolved' },
  ];

  return (
    <AdminShell active="reports">
      <H1>Reports</H1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {reports.map((r, i) => (
          <div key={i} style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: '18px 20px', display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontFamily: F.sans, fontSize: 15, fontWeight: 700, color: C.text }}>{r.type}</span>
                <span style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>{r.ref}</span>
              </div>
              <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, margin: 0, lineHeight: 1.55 }}>{r.note}</p>
            </div>
            <div style={{ flexShrink: 0 }}>
              <StatusBadge type={r.status === 'Under review' ? 'available' : 'neutral'}>{r.status}</StatusBadge>
            </div>
          </div>
        ))}
      </div>
    </AdminShell>
  );
}
