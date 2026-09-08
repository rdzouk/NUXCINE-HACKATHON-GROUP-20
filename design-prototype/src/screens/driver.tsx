import { useState } from 'react';
import { C, F } from '../tokens';
import {
  PrimaryBtn, SecondaryBtn, SOSBtn, MapBox, Stars, StatusBadge,
  Eyebrow, H1, H2, H3, SmallLabel, MobileScreen, ScrollArea,
  TopBar, RideSummaryCard, StatCard, DriverBottomNav,
} from '../ui';

export function DriverDashboardScreen() {
  const [available, setAvailable] = useState(true);

  return (
    <MobileScreen>
      <TopBar
        left={<H1 style={{ margin: 0, fontSize: 24 }}>Driver dashboard</H1>}
        right={
          <div onClick={() => setAvailable(a => !a)} style={{ cursor: 'pointer' }}>
            <StatusBadge type={available ? 'available' : 'offline'}>
              {available ? 'Available' : 'Offline'}
            </StatusBadge>
          </div>
        }
      />
      <ScrollArea paddingTop={0} paddingBottom={72}>
        <div style={{
          backgroundColor: available ? `${C.primary}10` : C.muted,
          border: `1px solid ${available ? C.primary + '35' : C.border}`,
          borderRadius: 8,
          padding: '14px 16px',
          marginBottom: 24,
        }}>
          <span style={{ fontFamily: F.sans, fontSize: 14, color: available ? C.primary : C.accent, fontWeight: 700 }}>
            {available ? '🟢 Online — accepting ride requests' : '⚫ Offline — not receiving requests'}
          </span>
          {available && (
            <div style={{ fontFamily: F.sans, fontSize: 13, color: C.accent, marginTop: 4 }}>
              Waiting for incoming requests...
            </div>
          )}
        </div>

        <SmallLabel>Today</SmallLabel>
        <div style={{ display: 'flex', gap: 10, marginTop: 10, marginBottom: 24 }}>
          <StatCard value="7" label="Rides" />
          <StatCard value="8 400" label="XAF earned" />
          <StatCard value="4.9" label="Rating" />
        </div>

        <SmallLabel>Recent rides</SmallLabel>
        <div style={{ marginTop: 10 }}>
          {[
            { from: 'Akwa', to: 'Bonabéri', fare: '1 100 XAF', time: '14:32' },
            { from: 'Bali', to: 'Marché Central', fare: '900 XAF', time: '12:15' },
            { from: 'Deïdo', to: 'Akwa', fare: '700 XAF', time: '10:04' },
          ].map((ride, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
              <div>
                <div style={{ fontFamily: F.sans, fontSize: 14, color: C.text, fontWeight: 700 }}>{ride.from} → {ride.to}</div>
                <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>{ride.time}</div>
              </div>
              <span style={{ fontFamily: F.sans, fontSize: 14, color: C.primary, fontWeight: 700 }}>{ride.fare}</span>
            </div>
          ))}
        </div>
      </ScrollArea>
      <DriverBottomNav active="dashboard" />
    </MobileScreen>
  );
}

export function DriverIncomingRequestScreen() {
  return (
    <MobileScreen>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '54px 24px 32px' }}>
        <div style={{
          width: 60,
          height: 60,
          borderRadius: '50%',
          backgroundColor: `${C.gold}20`,
          border: `2px solid ${C.gold}50`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 26,
          marginBottom: 16,
        }}>
          🔔
        </div>

        <H2 style={{ textAlign: 'center', marginBottom: 20 }}>New ride request</H2>

        <RideSummaryCard rows={[
          { label: 'Passenger', value: 'Aminata B.' },
          { label: 'Pickup', value: 'Rue de la Réunification' },
          { label: 'Drop-off', value: 'Marché Central, Akwa' },
          { label: 'Distance', value: '4.3 km' },
          { label: 'Fare', value: '1 200 XAF', bold: true },
        ]} />

        <p style={{ fontFamily: F.sans, fontSize: 13, color: C.danger, fontWeight: 700, marginBottom: 20, textAlign: 'center' }}>
          ⏱ Request expires in 15 seconds
        </p>

        <div style={{ display: 'flex', gap: 12, width: '100%' }}>
          <SecondaryBtn style={{ flex: 1 }}>Decline</SecondaryBtn>
          <PrimaryBtn style={{ flex: 1 }}>Accept</PrimaryBtn>
        </div>
      </div>
    </MobileScreen>
  );
}

export function DriverRideAcceptedScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <Eyebrow>Ride accepted</Eyebrow>
        <H1>Head to pickup</H1>

        <div style={{
          backgroundColor: `${C.primary}10`,
          border: `1px solid ${C.primary}35`,
          borderRadius: 8,
          padding: '16px',
          marginBottom: 20,
          display: 'flex',
          gap: 12,
        }}>
          <span style={{ fontSize: 20, flexShrink: 0 }}>📍</span>
          <div>
            <SmallLabel>Pickup location</SmallLabel>
            <div style={{ fontFamily: F.sans, fontSize: 15, color: C.text, fontWeight: 700, marginTop: 4 }}>
              Rue de la Réunification, Akwa, Douala
            </div>
          </div>
        </div>

        <H3>Passenger details</H3>
        <div style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', backgroundColor: C.bgAlt, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
              👤
            </div>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 15, fontWeight: 700, color: C.text }}>Aminata Bello</div>
              <Stars filled={5} size={14} />
              <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, marginTop: 2 }}>4.8 rating · 47 rides</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <SecondaryBtn style={{ flex: 1 }}>💬 Message</SecondaryBtn>
            <SecondaryBtn style={{ flex: 1 }}>📞 Call</SecondaryBtn>
          </div>
        </div>

        <PrimaryBtn fullWidth>Start navigation</PrimaryBtn>
      </ScrollArea>
    </MobileScreen>
  );
}

export function DriverNavigationScreen() {
  return (
    <MobileScreen>
      <MapBox height={340} />
      <div style={{ flex: 1, backgroundColor: C.surface, borderRadius: '20px 20px 0 0', marginTop: -20, padding: '20px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: C.border, margin: '0 auto 16px', opacity: 0.5 }} />

        <Eyebrow>Navigation active</Eyebrow>
        <h2 style={{ fontFamily: F.serif, fontSize: 22, color: C.text, margin: '0 0 4px 0' }}>Heading to pickup</h2>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 16 }}>
          Rue de la Réunification, Akwa, Douala
        </p>

        <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
          <div style={{ flex: 1, textAlign: 'center', backgroundColor: C.muted, borderRadius: 8, padding: '10px', border: `1px solid ${C.border}` }}>
            <SmallLabel>Distance</SmallLabel>
            <div style={{ fontFamily: F.serif, fontSize: 22, color: C.text, marginTop: 4 }}>1.8 km</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', backgroundColor: C.muted, borderRadius: 8, padding: '10px', border: `1px solid ${C.border}` }}>
            <SmallLabel>ETA</SmallLabel>
            <div style={{ fontFamily: F.serif, fontSize: 22, color: C.text, marginTop: 4 }}>4 min</div>
          </div>
        </div>

        <PrimaryBtn fullWidth>Arrived at pickup</PrimaryBtn>
        <div style={{ marginTop: 10 }}>
          <SecondaryBtn fullWidth>Cancel ride</SecondaryBtn>
        </div>
      </div>
    </MobileScreen>
  );
}

export function DriverRideInProgressScreen() {
  const [phase, setPhase] = useState<'pin' | 'riding'>('pin');

  return (
    <MobileScreen>
      {phase === 'pin' ? (
        <ScrollArea>
          <Eyebrow>Passenger present</Eyebrow>
          <H2>Verify ride PIN</H2>
          <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 28 }}>
            Ask the passenger for their 4-digit PIN to start the ride.
          </p>

          <div style={{ display: 'flex', gap: 10, marginBottom: 28, justifyContent: 'center' }}>
            {[0, 1, 2, 3].map(i => (
              <div key={i} style={{
                width: 58,
                height: 60,
                borderRadius: 8,
                backgroundColor: C.surface,
                border: `2px solid ${C.border}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: F.serif,
                fontSize: 28,
                color: C.text,
              }}>
                ·
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 24 }}>
            {['1','2','3','4','5','6','7','8','9','','0','⌫'].map((n, i) => (
              <div key={i} style={{
                height: 54,
                borderRadius: 8,
                backgroundColor: n ? C.surface : 'transparent',
                border: n ? `1px solid ${C.border}` : 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: F.sans,
                fontSize: 20,
                color: C.text,
                cursor: n ? 'pointer' : 'default',
              }}>
                {n}
              </div>
            ))}
          </div>

          <PrimaryBtn fullWidth onClick={() => setPhase('riding')}>Start ride</PrimaryBtn>
        </ScrollArea>
      ) : (
        <ScrollArea>
          <Eyebrow>Ride in progress</Eyebrow>
          <H2>Heading to destination</H2>
          <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 20 }}>
            Marché Central, Akwa, Douala
          </p>

          <div style={{
            backgroundColor: `${C.primary}10`,
            borderRadius: 8,
            padding: '16px',
            border: `1px solid ${C.primary}35`,
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'space-between',
          }}>
            <div>
              <SmallLabel>Distance remaining</SmallLabel>
              <div style={{ fontFamily: F.serif, fontSize: 24, color: C.text, marginTop: 4 }}>3.1 km</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <SmallLabel>ETA</SmallLabel>
              <div style={{ fontFamily: F.serif, fontSize: 24, color: C.text, marginTop: 4 }}>8 min</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
            <SecondaryBtn style={{ flex: 1 }}>💬 Message</SecondaryBtn>
            <SecondaryBtn style={{ flex: 1 }}>🆘 Emergency</SecondaryBtn>
          </div>

          <PrimaryBtn fullWidth onClick={() => setPhase('pin')}>End ride</PrimaryBtn>
        </ScrollArea>
      )}
    </MobileScreen>
  );
}

export function DriverEndRideScreen() {
  return (
    <MobileScreen>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '54px 32px 40px' }}>
        <div style={{
          width: 72,
          height: 72,
          borderRadius: '50%',
          backgroundColor: `${C.primary}15`,
          border: `2px solid ${C.primary}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 32,
          marginBottom: 22,
          color: C.primary,
        }}>
          ✓
        </div>

        <H1 style={{ textAlign: 'center', marginBottom: 8 }}>Ride completed</H1>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginBottom: 24 }}>
          Great work, Koffi! Here is your earnings summary.
        </p>

        <div style={{ width: '100%', backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden', marginBottom: 24 }}>
          {[
            { label: 'Fare collected', value: '1 200 XAF', bold: false },
            { label: 'VORA commission (15%)', value: '− 180 XAF', bold: false },
            { label: 'Your earnings', value: '1 020 XAF', bold: true },
          ].map(({ label, value, bold }, i) => (
            <div key={label} style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '14px 16px',
              borderBottom: i < 2 ? `1px solid ${C.border}` : 'none',
              backgroundColor: bold ? `${C.primary}08` : C.surface,
            }}>
              <span style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, fontWeight: bold ? 700 : 400 }}>{label}</span>
              <span style={{ fontFamily: F.sans, fontSize: 14, color: bold ? C.primary : C.text, fontWeight: bold ? 700 : 400 }}>{value}</span>
            </div>
          ))}
        </div>

        <PrimaryBtn fullWidth>Back to dashboard</PrimaryBtn>
      </div>
    </MobileScreen>
  );
}

export function DriverEarningsScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={72}>
        <H1>Earnings</H1>
        <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <StatCard value="48 200" label="XAF this week" />
          <StatCard value="23" label="Rides" />
        </div>

        <SmallLabel>Recent payouts</SmallLabel>
        <div style={{ marginTop: 12 }}>
          {[
            { route: 'Akwa → Marché Central', date: '5 Sep', amount: '1 020 XAF' },
            { route: 'Bastos → Nsimalen', date: '5 Sep', amount: '2 975 XAF' },
            { route: 'Bali → Bonabéri', date: '4 Sep', amount: '765 XAF' },
            { route: 'Essos → Mvog-Mbi', date: '4 Sep', amount: '552 XAF' },
            { route: 'Deïdo → Akwa', date: '3 Sep', amount: '595 XAF' },
          ].map((ride, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
              <div>
                <div style={{ fontFamily: F.sans, fontSize: 14, color: C.text, fontWeight: 700 }}>{ride.route}</div>
                <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>{ride.date}</div>
              </div>
              <span style={{ fontFamily: F.sans, fontSize: 14, color: C.primary, fontWeight: 700 }}>{ride.amount}</span>
            </div>
          ))}
        </div>
      </ScrollArea>
      <DriverBottomNav active="earnings" />
    </MobileScreen>
  );
}

export function DriverHistoryScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={72}>
        <H1>Ride history</H1>
        {[
          { from: 'Akwa', to: 'Marché Central', date: '5 Sep 2026', passenger: 'Aminata B.', fare: '1 200 XAF' },
          { from: 'Bastos', to: 'Nsimalen Airport', date: '5 Sep 2026', passenger: 'Jean K.', fare: '3 500 XAF' },
          { from: 'Bali', to: 'Bonabéri', date: '4 Sep 2026', passenger: 'Marie F.', fare: '900 XAF' },
          { from: 'Essos', to: 'Mvog-Mbi', date: '4 Sep 2026', passenger: 'Pierre N.', fare: '650 XAF' },
        ].map((ride, i) => (
          <div key={i} style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 14, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <SmallLabel>{ride.date}</SmallLabel>
              <span style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: C.primary }}>{ride.fare}</span>
            </div>
            <div style={{ fontFamily: F.sans, fontSize: 14, color: C.text, fontWeight: 700 }}>{ride.from} → {ride.to}</div>
            <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, marginTop: 3 }}>Passenger: {ride.passenger}</div>
          </div>
        ))}
      </ScrollArea>
      <DriverBottomNav active="history" />
    </MobileScreen>
  );
}

export function DriverProfileScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={72}>
        <H1>Driver profile</H1>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', backgroundColor: C.bgAlt, border: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, flexShrink: 0 }}>
            👤
          </div>
          <div>
            <div style={{ fontFamily: F.serif, fontSize: 20, color: C.text, marginBottom: 4 }}>Koffi Mensah</div>
            <Stars filled={5} size={16} />
            <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, marginTop: 3 }}>4.9 driver rating</div>
          </div>
        </div>

        {[
          { label: 'Phone', value: '+237 699 456 789' },
          { label: 'Vehicle', value: 'Toyota Corolla 2019' },
          { label: 'Plate', value: 'CM 4521 AD' },
          { label: 'License', value: 'DL-CM-00892' },
          { label: 'Active since', value: 'January 2025' },
          { label: 'Total rides', value: '312 rides' },
        ].map(row => (
          <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
            <SmallLabel>{row.label}</SmallLabel>
            <span style={{ fontFamily: F.sans, fontSize: 15, color: C.text }}>{row.value}</span>
          </div>
        ))}

        <div style={{ marginTop: 24 }}>
          <SecondaryBtn fullWidth>Edit profile</SecondaryBtn>
        </div>
      </ScrollArea>
      <DriverBottomNav active="profile" />
    </MobileScreen>
  );
}

export function DriverSafetyScreen() {
  return (
    <MobileScreen>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '54px 24px 40px' }}>
        <div style={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          backgroundColor: `${C.danger}12`,
          border: `2px solid ${C.danger}40`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 26,
          marginBottom: 18,
        }}>
          🛡️
        </div>

        <H1 style={{ textAlign: 'center', marginBottom: 8 }}>Safety</H1>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginBottom: 28, lineHeight: 1.6 }}>
          Your safety is our priority. Use these tools at any time.
        </p>

        <div style={{ width: '100%', marginBottom: 16 }}>
          <SOSBtn>🆘 Trigger emergency alert</SOSBtn>
        </div>

        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <SecondaryBtn fullWidth>⚠️ Report a passenger</SecondaryBtn>
          <SecondaryBtn fullWidth>📞 Contact assistance</SecondaryBtn>
          <SecondaryBtn fullWidth>📤 Share this ride</SecondaryBtn>
        </div>

        <p style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, textAlign: 'center', marginTop: 24, lineHeight: 1.7 }}>
          Emergency lines: <strong>117</strong> (Police) · <strong>118</strong> (Fire) · <strong>119</strong> (Medical)
        </p>
      </div>
    </MobileScreen>
  );
}
