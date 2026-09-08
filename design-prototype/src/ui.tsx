import { C, F } from './tokens';

// ── Buttons ──────────────────────────────────────────────────────────────────

type BtnProps = {
  children?: React.ReactNode;
  onClick?: () => void;
  fullWidth?: boolean;
  style?: React.CSSProperties;
  disabled?: boolean;
};

export function PrimaryBtn({ children, onClick, fullWidth, style, disabled }: BtnProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        backgroundColor: C.primary,
        color: '#fff',
        fontFamily: F.sans,
        fontSize: 15,
        fontWeight: 700,
        padding: '12px 20px',
        borderRadius: 8,
        border: 'none',
        cursor: 'pointer',
        width: fullWidth ? '100%' : 'auto',
        display: 'block',
        textAlign: 'center',
        opacity: disabled ? 0.55 : 1,
        transition: 'background-color 0.15s',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function SecondaryBtn({ children, onClick, fullWidth, style }: BtnProps) {
  return (
    <button
      onClick={onClick}
      style={{
        backgroundColor: C.muted,
        color: C.text,
        fontFamily: F.sans,
        fontSize: 15,
        fontWeight: 700,
        padding: '12px 20px',
        borderRadius: 8,
        border: `1px solid ${C.border}`,
        cursor: 'pointer',
        width: fullWidth ? '100%' : 'auto',
        display: 'block',
        textAlign: 'center',
        transition: 'background-color 0.15s',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function SOSBtn({ children = 'Trigger emergency alert', onClick }: { children?: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        backgroundColor: C.danger,
        color: '#fff',
        fontFamily: F.sans,
        fontSize: 15,
        fontWeight: 700,
        padding: '14px 20px',
        borderRadius: 8,
        border: 'none',
        cursor: 'pointer',
        width: '100%',
        display: 'block',
        textAlign: 'center',
        letterSpacing: '0.02em',
      }}
    >
      {children}
    </button>
  );
}

// ── Typography ────────────────────────────────────────────────────────────────

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: C.accent, margin: '0 0 6px 0', lineHeight: 1.4 }}>
      {children}
    </p>
  );
}

export function H1({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <h1 style={{ fontFamily: F.serif, fontSize: 32, fontWeight: 400, color: C.text, margin: '0 0 20px 0', lineHeight: 1.2, ...style }}>
      {children}
    </h1>
  );
}

export function H2({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <h2 style={{ fontFamily: F.serif, fontSize: 24, fontWeight: 400, color: C.text, margin: '0 0 14px 0', lineHeight: 1.3, ...style }}>
      {children}
    </h2>
  );
}

export function H3({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <h3 style={{ fontFamily: F.serif, fontSize: 18, fontWeight: 400, color: C.text, margin: '0 0 8px 0', lineHeight: 1.4, ...style }}>
      {children}
    </h3>
  );
}

export function SmallLabel({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontFamily: F.sans, fontSize: 12, fontWeight: 700, color: C.accent, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {children}
    </span>
  );
}

// ── Inputs ────────────────────────────────────────────────────────────────────

type InputProps = {
  label?: string;
  placeholder?: string;
  type?: string;
  defaultValue?: string;
};

export function TextInput({ label, placeholder, type = 'text', defaultValue }: InputProps) {
  return (
    <div style={{ marginBottom: 14 }}>
      {label && (
        <label style={{ fontFamily: F.sans, fontSize: 11, fontWeight: 700, color: C.accent, display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {label}
        </label>
      )}
      <input
        type={type}
        placeholder={placeholder}
        defaultValue={defaultValue}
        style={{
          width: '100%',
          backgroundColor: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 6,
          padding: '10px 12px',
          fontFamily: F.sans,
          fontSize: 15,
          color: C.text,
          outline: 'none',
        }}
      />
    </div>
  );
}

// ── Map ───────────────────────────────────────────────────────────────────────

export function MapBox({ height = 300, style }: { height?: number | string; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        width: '100%',
        height,
        backgroundColor: C.bgAlt,
        position: 'relative',
        overflow: 'hidden',
        flexShrink: 0,
        boxShadow: '0 18px 45px rgba(36,61,57,0.18)',
        ...style,
      }}
    >
      {/* Grid */}
      <svg viewBox="0 0 120 120" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.22 }}>
        {Array.from({ length: 13 }).map((_, i) => (
          <line key={`h${i}`} x1="0" y1={i * 10} x2="120" y2={i * 10} stroke="#285e55" strokeWidth="0.6" />
        ))}
        {Array.from({ length: 13 }).map((_, i) => (
          <line key={`v${i}`} x1={i * 10} y1="0" x2={i * 10} y2="120" stroke="#285e55" strokeWidth="0.6" />
        ))}
      </svg>

      {/* Route */}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        <path d="M 18 72 Q 38 28 62 45 Q 76 56 82 76" stroke={C.primary} strokeWidth="2.5" fill="none" strokeDasharray="9,5" opacity="0.8" strokeLinecap="round" />
        <circle cx="18" cy="72" r="3" fill={C.primary} />
        <circle cx="82" cy="76" r="3" fill={C.danger} />
        <circle cx="82" cy="76" r="6" fill="none" stroke={C.danger} strokeWidth="1.5" opacity="0.4" />
      </svg>

      {/* Label */}
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{
          fontFamily: F.sans,
          fontSize: 11,
          fontWeight: 700,
          color: C.accent,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          backgroundColor: `${C.surface}cc`,
          padding: '3px 10px',
          borderRadius: 4,
        }}>
          Map
        </span>
      </div>
    </div>
  );
}

// ── Stars ─────────────────────────────────────────────────────────────────────

export function Stars({ filled = 4, total = 5, size = 20 }: { filled?: number; total?: number; size?: number }) {
  return (
    <div style={{ display: 'flex', gap: 3 }}>
      {Array.from({ length: total }).map((_, i) => (
        <span key={i} style={{ fontSize: size, color: i < filled ? C.gold : '#cccccc', lineHeight: 1 }}>★</span>
      ))}
    </div>
  );
}

// ── Badges ────────────────────────────────────────────────────────────────────

type BadgeType = 'available' | 'offline' | 'neutral';

const badgeColors: Record<BadgeType, { bg: string; border: string; text: string; dot: string }> = {
  available: { bg: '#285e5518', border: '#285e55', text: '#285e55', dot: '#285e55' },
  offline:   { bg: '#f3f6f4',  border: '#a2bbb3', text: '#45756d', dot: '#a2bbb3' },
  neutral:   { bg: '#f3f6f4',  border: '#a2bbb3', text: '#45756d', dot: '#45756d' },
};

export function StatusBadge({ children, type = 'available' }: { children: React.ReactNode; type?: BadgeType }) {
  const col = badgeColors[type];
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '4px 12px',
      borderRadius: 999,
      border: `1px solid ${col.border}`,
      backgroundColor: col.bg,
      color: col.text,
      fontFamily: F.sans,
      fontSize: 12,
      fontWeight: 700,
      whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: col.dot, flexShrink: 0 }} />
      {children}
    </span>
  );
}

export function NotificationBadge({ count }: { count: number }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      minWidth: 20,
      height: 20,
      borderRadius: 999,
      backgroundColor: C.danger,
      color: '#fff',
      fontFamily: F.sans,
      fontSize: 11,
      fontWeight: 700,
      padding: '0 4px',
    }}>
      {count}
    </span>
  );
}

// ── Cards ─────────────────────────────────────────────────────────────────────

export function RideSummaryCard({ rows }: { rows: Array<{ label: string; value: string; bold?: boolean }> }) {
  return (
    <div style={{
      backgroundColor: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: 8,
      overflow: 'hidden',
      marginBottom: 16,
    }}>
      {rows.map(({ label, value, bold }, i) => (
        <div
          key={label}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px',
            borderBottom: i < rows.length - 1 ? `1px solid ${C.border}` : 'none',
            backgroundColor: bold ? C.muted : C.surface,
          }}
        >
          <SmallLabel>{label}</SmallLabel>
          <span style={{ fontFamily: F.sans, fontSize: 15, color: C.text, fontWeight: bold ? 700 : 400 }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

export function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div style={{
      backgroundColor: C.muted,
      borderRadius: 8,
      padding: '22px 16px',
      textAlign: 'center',
      flex: 1,
      border: `1px solid ${C.border}`,
    }}>
      <div style={{ fontFamily: F.serif, fontSize: 34, fontWeight: 400, color: C.text, marginBottom: 6, lineHeight: 1 }}>{value}</div>
      <SmallLabel>{label}</SmallLabel>
    </div>
  );
}

// ── Bottom Nav ────────────────────────────────────────────────────────────────

type NavItem = { id: string; label: string; icon: string };

function BottomNavBar({ items, activeId }: { items: NavItem[]; activeId: string }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      backgroundColor: C.surface,
      borderTop: `1px solid ${C.border}`,
      display: 'flex',
      paddingBottom: 8,
      zIndex: 10,
    }}>
      {items.map(item => (
        <div key={item.id} style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 8,
          color: item.id === activeId ? C.primary : C.accent,
          gap: 3,
          cursor: 'pointer',
        }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>{item.icon}</span>
          <span style={{ fontFamily: F.sans, fontSize: 10, fontWeight: 700, letterSpacing: '0.03em' }}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function PassengerBottomNav({ active = 'home' }: { active?: string }) {
  return (
    <BottomNavBar
      activeId={active}
      items={[
        { id: 'home', label: 'Home', icon: '⌂' },
        { id: 'history', label: 'History', icon: '◷' },
        { id: 'profile', label: 'Profile', icon: '◯' },
      ]}
    />
  );
}

export function DriverBottomNav({ active = 'dashboard' }: { active?: string }) {
  return (
    <BottomNavBar
      activeId={active}
      items={[
        { id: 'dashboard', label: 'Dashboard', icon: '◉' },
        { id: 'earnings', label: 'Earnings', icon: '₣' },
        { id: 'history', label: 'History', icon: '◷' },
        { id: 'profile', label: 'Profile', icon: '◯' },
      ]}
    />
  );
}

// ── Admin Sidebar ─────────────────────────────────────────────────────────────

const adminNavItems = [
  { id: 'dashboard', label: 'Dashboard', icon: '◉' },
  { id: 'users',     label: 'Users',     icon: '◯' },
  { id: 'drivers',   label: 'Drivers',   icon: '◈' },
  { id: 'rides',     label: 'Rides',     icon: '→' },
  { id: 'stats',     label: 'Statistics',icon: '▦' },
  { id: 'reports',   label: 'Reports',   icon: '☐' },
];

export function AdminSidebar({ active }: { active: string }) {
  return (
    <div style={{
      width: 200,
      minHeight: '100%',
      backgroundColor: C.sidebar,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      <div style={{ padding: '28px 20px 20px' }}>
        <div style={{ fontFamily: F.serif, fontSize: 22, fontWeight: 400, color: '#fff', letterSpacing: '0.04em' }}>VORA</div>
        <div style={{ fontFamily: F.sans, fontSize: 10, color: 'rgba(255,255,255,0.4)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', marginTop: 4 }}>
          Admin Panel
        </div>
      </div>
      <nav style={{ padding: '0 10px', flex: 1 }}>
        {adminNavItems.map(item => (
          <div
            key={item.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 2,
              backgroundColor: item.id === active ? C.primary : 'transparent',
              color: item.id === active ? '#fff' : 'rgba(255,255,255,0.6)',
              fontFamily: F.sans,
              fontSize: 13,
              fontWeight: item.id === active ? 700 : 400,
              cursor: 'pointer',
              transition: 'background-color 0.15s',
            }}
          >
            <span style={{ fontSize: 13, width: 18, textAlign: 'center', flexShrink: 0 }}>{item.icon}</span>
            {item.label}
          </div>
        ))}
      </nav>
      <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ fontFamily: F.sans, fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>v1.0 — Sep 2026</div>
      </div>
    </div>
  );
}

// ── Layout helpers ────────────────────────────────────────────────────────────

export function MobileScreen({ children, bg, style }: { children: React.ReactNode; bg?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      backgroundColor: bg ?? C.bg,
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      fontFamily: F.sans,
      color: C.text,
      ...style,
    }}>
      {children}
    </div>
  );
}

export function TopBar({ left, right }: { left?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      padding: '54px 20px 12px',
      flexShrink: 0,
    }}>
      <div style={{ flex: 1 }}>{left}</div>
      <div style={{ flexShrink: 0, marginLeft: 12 }}>{right}</div>
    </div>
  );
}

export function ScrollArea({ children, style, paddingBottom = 80, paddingTop = 64 }: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  paddingBottom?: number;
  paddingTop?: number;
}) {
  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: `${paddingTop}px 20px ${paddingBottom}px`,
      ...style,
    }}>
      {children}
    </div>
  );
}

export function ListRow({ icon, title, subtitle, right, dimmed = false }: {
  icon?: string;
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  dimmed?: boolean;
}) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '14px 0',
      borderBottom: `1px solid ${C.border}`,
      opacity: dimmed ? 0.5 : 1,
    }}>
      {icon && (
        <div style={{
          width: 40,
          height: 40,
          borderRadius: '50%',
          backgroundColor: C.muted,
          border: `1px solid ${C.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          flexShrink: 0,
        }}>
          {icon}
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: F.sans, fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 2 }}>{title}</div>
        {subtitle && <div style={{ fontFamily: F.sans, fontSize: 12, color: C.accent }}>{subtitle}</div>}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}
