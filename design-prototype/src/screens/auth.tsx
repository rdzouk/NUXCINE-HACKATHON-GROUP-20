import { C, F } from '../tokens';
import { PrimaryBtn, TextInput, H1, H3, Eyebrow, MobileScreen, ScrollArea } from '../ui';

export function SplashScreen() {
  return (
    <MobileScreen bg={C.primary}>
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 36px 40px',
      }}>
        <div style={{
          width: 76,
          height: 76,
          borderRadius: '50%',
          border: '1.5px solid rgba(255,255,255,0.35)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 28,
        }}>
          <span style={{ fontFamily: F.serif, fontSize: 30, color: '#fff', fontWeight: 400, letterSpacing: '0.02em' }}>V</span>
        </div>

        <h1 style={{ fontFamily: F.serif, fontSize: 56, fontWeight: 400, color: '#fff', margin: '0 0 10px 0', letterSpacing: '-0.01em', lineHeight: 1 }}>
          VORA
        </h1>
        <p style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.65)', margin: '0 0 60px 0', textAlign: 'center' }}>
          Smart mobility for Cameroon
        </p>

        <div style={{ width: '100%' }}>
          <button style={{
            width: '100%',
            backgroundColor: '#fff',
            color: C.primary,
            fontFamily: F.sans,
            fontSize: 15,
            fontWeight: 700,
            padding: '14px 20px',
            borderRadius: 8,
            border: 'none',
            cursor: 'pointer',
            marginBottom: 10,
          }}>
            Get started
          </button>
          <button style={{
            width: '100%',
            backgroundColor: 'transparent',
            color: 'rgba(255,255,255,0.8)',
            fontFamily: F.sans,
            fontSize: 15,
            fontWeight: 700,
            padding: '13px 20px',
            borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.3)',
            cursor: 'pointer',
          }}>
            Log in
          </button>
        </div>
      </div>
      <div style={{ padding: '0 36px 28px', textAlign: 'center' }}>
        <p style={{ fontFamily: F.sans, fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0, lineHeight: 1.6 }}>
          By continuing you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </MobileScreen>
  );
}

export function LoginScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontFamily: F.serif, fontSize: 13, color: C.accent, letterSpacing: '0.04em' }}>VORA</span>
        </div>
        <H1>Log in</H1>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 28, marginTop: -14, lineHeight: 1.5 }}>
          Welcome back. Enter your details to continue.
        </p>

        <TextInput label="Phone number" placeholder="+237 6XX XXX XXX" type="tel" />
        <TextInput label="Password" placeholder="••••••••" type="password" />

        <div style={{ marginTop: 8, marginBottom: 20 }}>
          <PrimaryBtn fullWidth>Log in</PrimaryBtn>
        </div>

        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginBottom: 8 }}>
          New to VORA?{' '}
          <span style={{ color: C.primary, fontWeight: 700, cursor: 'pointer' }}>Sign up</span>
        </p>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center' }}>
          <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Forgot password?</span>
        </p>
      </ScrollArea>
    </MobileScreen>
  );
}

export function SignupScreen() {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontFamily: F.serif, fontSize: 13, color: C.accent, letterSpacing: '0.04em' }}>VORA</span>
        </div>
        <H1>Create account</H1>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, marginBottom: 28, marginTop: -14, lineHeight: 1.5 }}>
          Join thousands of riders across Cameroon.
        </p>

        <TextInput label="Full name" placeholder="Aminata Bello" />
        <TextInput label="Phone number" placeholder="+237 6XX XXX XXX" type="tel" />
        <TextInput label="Password" placeholder="Create a password" type="password" />

        <div style={{ marginTop: 8, marginBottom: 16 }}>
          <PrimaryBtn fullWidth>Sign up</PrimaryBtn>
        </div>

        <p style={{ fontFamily: F.sans, fontSize: 12, color: C.accent, textAlign: 'center', lineHeight: 1.6 }}>
          By signing up you agree to our{' '}
          <span style={{ color: C.primary, fontWeight: 700 }}>Terms of Service</span> and{' '}
          <span style={{ color: C.primary, fontWeight: 700 }}>Privacy Policy</span>.
        </p>
        <p style={{ fontFamily: F.sans, fontSize: 14, color: C.accent, textAlign: 'center', marginTop: 14 }}>
          Already have an account?{' '}
          <span style={{ color: C.primary, fontWeight: 700, cursor: 'pointer' }}>Log in</span>
        </p>
      </ScrollArea>
    </MobileScreen>
  );
}

const privacySections = [
  {
    title: 'What we collect',
    body: "We collect your name, phone number, location data, and ride history to provide the VORA service. Location is only collected during active sessions.",
  },
  {
    title: 'Why we collect it',
    body: "Your data enables ride matching, payment processing, safety monitoring, and service improvement. We do not sell your data to third parties.",
  },
  {
    title: 'Who sees it',
    body: "Drivers see your first name and pickup location. Passengers see driver name, vehicle, and rating. Admins access all data for safety and compliance.",
  },
  {
    title: 'SOS data',
    body: "When you activate the SOS feature, your real-time location and ride details are immediately shared with our safety team and designated emergency contacts.",
  },
  {
    title: 'Retention',
    body: "We retain your account data for as long as you maintain an active account, plus 2 years after deletion for legal compliance. Ride data is retained for 5 years.",
  },
  {
    title: 'Contact',
    body: "For data requests, corrections, or deletion inquiries, contact our privacy team at privacy@vora.cm or call +237 222 000 100.",
  },
];

const termsSections = [
  {
    title: 'What VORA is',
    body: "VORA is a technology platform connecting passengers with independent driver-partners in Cameroon. VORA facilitates the connection; drivers are independent contractors.",
  },
  {
    title: 'Using the app',
    body: "You must be at least 18 years old to use VORA. You are responsible for maintaining the confidentiality of your account credentials.",
  },
  {
    title: 'Payment',
    body: "Fares are calculated based on distance and duration. Payment is processed at ride completion. Prices include a 15% platform commission retained by VORA.",
  },
  {
    title: 'Conduct & safety',
    body: "All users must treat drivers and passengers with respect. Threatening, abusive, or discriminatory behavior will result in immediate account suspension.",
  },
  {
    title: 'Cancellations',
    body: "Passengers may cancel within 3 minutes of driver acceptance at no charge. Late cancellations incur a 500 XAF fee. Drivers may cancel in exceptional circumstances.",
  },
  {
    title: 'Changes',
    body: "VORA may update these terms at any time. Continued use of the app after notification of changes constitutes acceptance of the revised terms.",
  },
];

function LegalScreen({ title, eyebrow, sections }: {
  title: string;
  eyebrow: string;
  sections: typeof privacySections;
}) {
  return (
    <MobileScreen>
      <ScrollArea paddingBottom={24}>
        <Eyebrow>{eyebrow}</Eyebrow>
        <H1>{title}</H1>
        {sections.map(section => (
          <div key={section.title} style={{ marginBottom: 24 }}>
            <H3>{section.title}</H3>
            <p style={{ fontFamily: F.sans, fontSize: 15, color: C.text, lineHeight: 1.65, margin: 0 }}>
              {section.body}
            </p>
          </div>
        ))}
      </ScrollArea>
    </MobileScreen>
  );
}

export function PrivacyScreen() {
  return <LegalScreen title="Privacy Policy" eyebrow="Last updated: September 2026" sections={privacySections} />;
}

export function TermsScreen() {
  return <LegalScreen title="Terms of Service" eyebrow="Last updated: September 2026" sections={termsSections} />;
}
