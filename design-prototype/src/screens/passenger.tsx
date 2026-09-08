import { C, F } from '../tokens';
import {
  PrimaryBtn, SecondaryBtn, SOSBtn, TextInput, MapBox, Stars,
  StatusBadge, NotificationBadge, Eyebrow, H1, H2, H3, SmallLabel,
  MobileScreen, ScrollArea, TopBar, ListRow, RideSummaryCard, PassengerBottomNav,
} from '../ui';

export function PassengerHomeScreen() {
  return (
    <MobileScreen>
      <TopBar
        left={
          <div>
            <Eyebrow>Bonjour, Aminata</Eyebrow>
            <h1 style={{ fontFamily: F.serif, fontSize: 26, fontWeight: 400, color: C.text, margin: 0, lineHeight: 1.2 }}>
              Where are you going?
            </h1>
          </div>
        }
        right={
          <div style={{ position: 'relative' }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: C.muted, border: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
              🔔
            </div>
            <div style={{ position: 'absolute', top: -4, right: -4 }}>
              <NotificationBadge count={3} />
            </div>
          </div>
        }
      />
      <ScrollArea paddingTop={0} paddingBottom={72}>
        <div style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: '13px 16px', display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24, cursor: 'text' }}>
          <span style={{ fontSize: 16 }}>🔍</span>
          <span style={{ fontFamily: F.sans, fontSize: 15, color: `${C.text}55` }}>Enter your destination</span>
        </div>

        <SmallLabel>Recent trips</SmallLabel>
        <div style={{ marginTop: 10 }}>
          <ListRow icon="⭐" title="Marché Central" subtitle="Douala, Wouri" right={<span style={{ color: C.accent }}>→</span>} />
          <ListRow icon="🏢" title="Aéroport de Nsimalen" subtitle="Yaoundé" right={<span style={{ color: C.accent }}>→</span>} />
          <ListRow icon="🏠" title="Quartier Bastos" subtitle="Yaoundé" right={<span style={{ color: C.accent }}>→</span>} />
        </div>

        <div style={{ marginTop: 24, backgroundColor: `${C.primary}10`, border: `1px solid ${C.primary}35`, borderRadius: 8, padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 22, flexShrink: 0 }}>🎉</span>
          <div>
            <div style={{ fontFamily: F.sans, fontSize: 13, fontWeight: 700, color: C.primary, marginBottom: 2 }}>20% off your next ride</div>
            <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>Use code VORA20 — expires 30 Sep 2026</div>
          </div>
        </div>
      </ScrollArea>
      <PassengerBottomNav active="home" />
    </MobileScreen>
  );
}

export function PassengerMapBookingScreen() {
  return (
    <MobileScreen>
      <MapBox height="60%" />
      <div style={{ flex: 1, backgroundColor: C.surface, borderRadius: '20px 20px 0 0', marginTop: -20, padding: '20px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: C.border, margin: '0 auto 16px', opacity: 0.5 }} />
        <TextInput label="Pickup" placeholder="📍 Current location" defaultValue="Rue de la Réunification, Douala" />
        <TextInput label="Destination" placeholder="🏁 Where to?" />

        <div style={{ backgroundColor: C.muted, borderRadius: 8, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, border: `1px solid ${C.border}` }}>
          <div>
            <SmallLabel>Estimated fare</SmallLabel>
            <div style={{ fontFamily: F.serif, fontSize: 22, color: C.text, marginTop: 3 }}>1 200 XAF</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <SmallLabel>Distance</SmallLabel>
            <div style={{ fontFamily: F.sans, fontSize: 15, color: C.text, marginTop: 3, fontWeight: 700 }}>4.3 km</div>
          </div>
        </div>

        <PrimaryBtn fullWidth>Confirm ride</PrimaryBtn>
      </div>
    </MobileScreen>
  );
}

export function PassengerConfirmScreen() {
  return (
    <MobileScreen>
      <ScrollArea>
        <Eyebrow>Almost there</Eyebrow>
        <H1>Confirm your ride</H1>

        <RideSummaryCard rows={[
          { label: 'From', value: 'Rue de la Réunification' },
          { label: 'To', value: 'Marché Central, Akwa' },
          { label: 'Distance', value: '4.3 km' },
          { label: 'Duration', value: '~12 min' },
          { label: 'Fare', value: '1 200 XAF', bold: true },
        ]} />

        <div style={{ backgroundColor: C.muted, borderRadius: 8, padding: '14px 16px', marginBottom: 20, border: `1px solid ${C.border}` }}>
          <SmallLabel>Payment method</SmallLabel>
          <div style={{ fontFamily: F.sans, fontSize: 15, color: C.text, marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>📱</span> MTN Mobile Money
          </div>
        </div>

        <PrimaryBtn fullWidth>Confirm ride</PrimaryBtn>
        <div style={{ marginTop: 10 }}>
          <SecondaryBtn fullWidth>Edit details</SecondaryBtn>
        </div>
      </ScrollArea>
    </MobileScreen>
  );
}

export function PassengerSearchingScreen() {
  return (
    <MobileScreen>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '54px 32px 40px' }}>
        <div style={{ position: 'relative', width: 120, height: 120, marginBottom: 32 }}>
          <div className="pulse-ring" style={{ position: 'absolute', inset: 0, borderRadius: '50%', backgroundColor: `${C.primary}10` }} />
          <div className="pulse-ring" style={{ position: 'absolute', inset: 18, borderRadius: '50%', backgroundColor: `${C.primary}15`, animationDelay: '0.35s' }} />
          <div className="pulse-dot" style={{ position: 'absolute', inset: 36, borderRadius: '50%', backgroundColor: C.primary, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>
            🚗
          </div>
        </div>

        <H2 style={{ textAlign: 'center', marginBottom: 8 }}>Looking for a driver...</H2>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginBottom: 36 }}>
          This won't take long
        </p>

        <div style={{ backgroundColor: C.muted, borderRadius: 8, padding: '14px 20px', border: `1px solid ${C.border}`, width: '100%', marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <SmallLabel>To</SmallLabel>
            <SmallLabel>Fare</SmallLabel>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: F.sans, fontSize: 14, color: C.text }}>Marché Central</span>
            <span style={{ fontFamily: F.sans, fontSize: 14, color: C.text, fontWeight: 700 }}>1 200 XAF</span>
          </div>
        </div>

        <SecondaryBtn fullWidth>Cancel search</SecondaryBtn>
      </div>
    </MobileScreen>
  );
}

export function PassengerDriverEnRouteScreen() {
  return (
    <MobileScreen>
      <MapBox height={280} />
      <div style={{ flex: 1, backgroundColor: C.surface, borderRadius: '20px 20px 0 0', marginTop: -20, padding: '20px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: C.border, margin: '0 auto 16px', opacity: 0.5 }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <Eyebrow>Driver on the way</Eyebrow>
            <h2 style={{ fontFamily: F.serif, fontSize: 30, color: C.text, margin: 0 }}>6 min away</h2>
          </div>
          <StatusBadge type="available">Pickup: Akwa</StatusBadge>
        </div>

        <div style={{ backgroundColor: C.muted, borderRadius: 8, padding: '14px 16px', border: `1px solid ${C.border}`, display: 'flex', gap: 14, alignItems: 'center', marginBottom: 16 }}>
          <div style={{ width: 52, height: 52, borderRadius: '50%', backgroundColor: C.bgAlt, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, flexShrink: 0 }}>
            👤
          </div>
          <div style={{ flex: 1 }}>
            <H3 style={{ margin: '0 0 3px 0' }}>Koffi Mensah</H3>
            <Stars filled={5} size={16} />
            <div style={{ fontFamily: F.sans, fontSize: 13, color: C.accent, marginTop: 3 }}>Toyota Corolla · CM 4521 AD</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <SecondaryBtn style={{ flex: 1 }}>💬 Message</SecondaryBtn>
          <SecondaryBtn style={{ flex: 1 }}>📞 Call</SecondaryBtn>
        </div>
      </div>
    </MobileScreen>
  );
}

export function PassengerRideInProgressScreen() {
  return (
    <MobileScreen>
      <MapBox height={340} />
      <div style={{ flex: 1, backgroundColor: C.surface, borderRadius: '20px 20px 0 0', marginTop: -20, padding: '20px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: C.border, margin: '0 auto 16px', opacity: 0.5 }} />

        <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 14 }}>
          <div style={{ width: 44, height: 44, borderRadius: '50%', backgroundColor: C.bgAlt, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
            👤
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: F.sans, fontSize: 15, fontWeight: 700, color: C.text }}>Koffi Mensah</div>
            <div style={{ fontFamily: F.sans, fontSize: 13, color: C.accent }}>Heading to Marché Central</div>
          </div>
          <Stars filled={5} size={14} />
        </div>

        <div style={{ backgroundColor: `${C.primary}10`, borderRadius: 8, padding: '12px 16px', border: `1px solid ${C.primary}30`, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span>🚗</span>
          <span style={{ fontFamily: F.sans, fontSize: 14, color: C.primary, fontWeight: 700 }}>Ride in progress — 3.1 km remaining</span>
        </div>

        <SOSBtn>🆘 Emergency — SOS</SOSBtn>
      </div>
    </MobileScreen>
  );
}

export function PassengerRideCompletedScreen() {
  return (
    <MobileScreen>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '54px 32px 40px' }}>
        <div style={{ width: 72, height: 72, borderRadius: '50%', backgroundColor: `${C.primary}15`, border: `2px solid ${C.primary}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 30, color: C.primary, marginBottom: 22 }}>
          ✓
        </div>

        <H1 style={{ textAlign: 'center', marginBottom: 8 }}>Ride completed</H1>

        <div style={{ backgroundColor: C.muted, borderRadius: 8, padding: '14px 28px', marginBottom: 24, textAlign: 'center', border: `1px solid ${C.border}` }}>
          <SmallLabel>Total fare</SmallLabel>
          <div style={{ fontFamily: F.serif, fontSize: 32, color: C.text, marginTop: 6 }}>1 200 XAF</div>
        </div>

        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginBottom: 10 }}>
          Rate your experience with Koffi
        </p>
        <Stars filled={5} size={36} />
        <p style={{ fontFamily: F.sans, fontSize: 13, color: C.accent, textAlign: 'center', marginTop: 6, marginBottom: 24 }}>
          Tap a star to rate
        </p>

        <PrimaryBtn fullWidth>Done</PrimaryBtn>
        <div style={{ marginTop: 10, width: '100%' }}>
          <SecondaryBtn fullWidth>Leave a comment</SecondaryBtn>
        </div>
      </div>
    </MobileScreen>
  );
}

const rideHistory = [
  { from: 'Akwa, Douala', to: 'Marché Central', date: '5 Sep 2026', fare: '1 200 XAF' },
  { from: 'Bastos, Yaoundé', to: 'Aéroport de Nsimalen', date: '2 Sep 2026', fare: '3 500 XAF' },
  { from: 'Bali, Douala', to: 'Bonabéri Bridge', date: '29 Aug 2026', fare: '900 XAF' },
  { from: 'Essos, Yaoundé', to: 'Mvog-Mbi Market', date: '24 Aug 2026', fare: '650 XAF' },
];

export function PassengerHistoryScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={72}>
        <H1>Ride history</H1>
        {rideHistory.map((ride, i) => (
          <div key={i} style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
              <SmallLabel>{ride.date}</SmallLabel>
              <span style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: C.text }}>{ride.fare}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: C.primary, flexShrink: 0 }} />
                <span style={{ fontFamily: F.sans, fontSize: 14, color: C.text }}>{ride.from}</span>
              </div>
              <div style={{ width: 1, height: 10, backgroundColor: C.border, marginLeft: 3.5 }} />
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: C.danger, flexShrink: 0 }} />
                <span style={{ fontFamily: F.sans, fontSize: 14, color: C.text }}>{ride.to}</span>
              </div>
            </div>
          </div>
        ))}
      </ScrollArea>
      <PassengerBottomNav active="history" />
    </MobileScreen>
  );
}

export function PassengerProfileScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={72}>
        <H1>Profile</H1>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', backgroundColor: C.bgAlt, border: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, flexShrink: 0 }}>
            👤
          </div>
          <div>
            <div style={{ fontFamily: F.serif, fontSize: 20, color: C.text, marginBottom: 4 }}>Aminata Bello</div>
            <Stars filled={5} size={16} />
            <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, marginTop: 3 }}>4.8 passenger rating</div>
          </div>
        </div>

        {[
          { label: 'Phone', value: '+237 677 890 123' },
          { label: 'Email', value: 'aminata.bello@email.cm' },
          { label: 'Member since', value: 'March 2025' },
          { label: 'Total rides', value: '47 rides' },
        ].map(row => (
          <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: `1px solid ${C.border}` }}>
            <SmallLabel>{row.label}</SmallLabel>
            <span style={{ fontFamily: F.sans, fontSize: 15, color: C.text }}>{row.value}</span>
          </div>
        ))}

        <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <SecondaryBtn fullWidth>Edit profile</SecondaryBtn>
          <SecondaryBtn fullWidth>Log out</SecondaryBtn>
        </div>

        <div style={{ marginTop: 20, display: 'flex', gap: 20, justifyContent: 'center' }}>
          <span style={{ fontFamily: F.sans, fontSize: 13, color: C.primary, fontWeight: 700, cursor: 'pointer' }}>Privacy Policy</span>
          <span style={{ fontFamily: F.sans, fontSize: 13, color: C.accent }}>·</span>
          <span style={{ fontFamily: F.sans, fontSize: 13, color: C.primary, fontWeight: 700, cursor: 'pointer' }}>Terms of Service</span>
        </div>
      </ScrollArea>
      <PassengerBottomNav active="profile" />
    </MobileScreen>
  );
}

export function PassengerSupportScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <H1>Support</H1>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 24, marginTop: -14, lineHeight: 1.5 }}>
          We are here to help. Reach us through any channel below.
        </p>

        {[
          { icon: '📞', label: 'Phone support', value: '+237 222 000 100', sub: 'Mon–Sat, 7am–9pm' },
          { icon: '📧', label: 'Email', value: 'support@vora.cm', sub: 'Response within 24 hours' },
          { icon: '💬', label: 'WhatsApp', value: '+237 677 000 200', sub: 'Mon–Sun, 8am–8pm' },
        ].map(item => (
          <div key={item.label} style={{ display: 'flex', gap: 14, alignItems: 'center', padding: '14px 0', borderBottom: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 24, flexShrink: 0 }}>{item.icon}</div>
            <div>
              <SmallLabel>{item.label}</SmallLabel>
              <div style={{ fontFamily: F.sans, fontSize: 15, color: C.text, fontWeight: 700, marginTop: 3 }}>{item.value}</div>
              <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>{item.sub}</div>
            </div>
          </div>
        ))}

        <div style={{ marginTop: 24 }}>
          <p style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 10 }}>Send us a message</p>
          <textarea
            placeholder="Describe your issue..."
            style={{ width: '100%', minHeight: 96, backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, padding: 10, fontFamily: F.sans, fontSize: 15, color: C.text, resize: 'none', outline: 'none', marginBottom: 12 }}
          />
          <PrimaryBtn fullWidth>Send message</PrimaryBtn>
        </div>
      </ScrollArea>
    </MobileScreen>
  );
}

const notifications = [
  { title: 'Ride confirmed', body: 'Koffi Mensah accepted your ride request. ETA: 6 minutes.', time: '2 min ago', read: false },
  { title: 'Promo: 20% off', body: 'Use code VORA20 on your next ride. Valid until 30 September 2026.', time: '1 hour ago', read: false },
  { title: 'Ride completed', body: 'Your ride to Marché Central was completed. Total: 1 200 XAF.', time: '3 hours ago', read: true },
  { title: 'Payment received', body: 'Payment of 3 500 XAF processed via MTN Mobile Money.', time: 'Yesterday', read: true },
  { title: 'Welcome to VORA', body: 'Thank you for joining VORA, the smart mobility platform for Cameroon.', time: '5 days ago', read: true },
];

export function PassengerNotificationsScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
          <H1>Notifications</H1>
          <span style={{ fontFamily: F.sans, fontSize: 13, color: C.primary, fontWeight: 700, cursor: 'pointer' }}>Mark all read</span>
        </div>
        {notifications.map((n, i) => (
          <div key={i} style={{ padding: '14px 0', borderBottom: `1px solid ${C.border}`, opacity: n.read ? 0.52 : 1, display: 'flex', gap: 12 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: n.read ? 'transparent' : C.primary, flexShrink: 0, marginTop: 6 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: F.sans, fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 3 }}>{n.title}</div>
              <div style={{ fontFamily: F.sans, fontSize: 13, color: C.accent, marginBottom: 4, lineHeight: 1.5 }}>{n.body}</div>
              <div style={{ fontFamily: F.sans, fontSize: 11, color: C.accent }}>{n.time}</div>
            </div>
          </div>
        ))}
      </ScrollArea>
    </MobileScreen>
  );
}
