import { useEffect, useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import OtpInput from '../components/OtpInput';
import { peekOtp, requestOtp, verifyOtp } from '../services/authApi';
import { getAccessToken, getRouteForRole, getStoredUser } from '../services/session';

function sanitizePhone(value) {
  const trimmed = value.trim();

  if (trimmed.startsWith('+')) {
    return `+${trimmed.slice(1).replace(/\D/g, '')}`;
  }

  return trimmed.replace(/\D/g, '');
}

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [code, setCode] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [resendAfterSeconds, setResendAfterSeconds] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [noticeMessage, setNoticeMessage] = useState('');
  const [devCode, setDevCode] = useState('');
  const [secondsLeft, setSecondsLeft] = useState(0);
  const navigate = useNavigate();

  const expiresLabel = useMemo(() => {
    if (!expiresAt) {
      return '';
    }

    return new Date(expiresAt).toLocaleTimeString();
  }, [expiresAt]);

  useEffect(() => {
    if (secondsLeft <= 0) {
      return undefined;
    }

    const timer = setInterval(() => setSecondsLeft((n) => Math.max(0, n - 1)), 1000);
    return () => clearInterval(timer);
  }, [secondsLeft]);

  useEffect(() => {
    const token = getAccessToken();
    const storedUser = getStoredUser();

    if (token && storedUser?.role) {
      navigate(getRouteForRole(storedUser.role), { replace: true });
    }
  }, [navigate]);

  async function handleRequestOtp() {
    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await requestOtp(phone.trim());
      setChallengeId(response.challenge_id);
      setExpiresAt(response.expires_at);
      setResendAfterSeconds(response.resend_after_s);
      setSecondsLeft(response.resend_after_s ?? 0);
      setCode('');
      setNoticeMessage('Enter the code that was sent to your phone.');

      // No SMS gateway is wired, so in development the server can hand
      // the code straight back. Returns null on a real deployment.
      setDevCode((await peekOtp(phone.trim())) ?? '');
    } catch (error) {
      setNoticeMessage('');
      setErrorMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleVerifyOtp() {
    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const session = await verifyOtp(challengeId, code.trim());
      navigate(getRouteForRole(session.user.role), { replace: true });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (challengeId) {
      await handleVerifyOtp();
      return;
    }

    await handleRequestOtp();
  };

  return (
    <main className="app-shell">
      <h1>Log in</h1>
      <p>Use your phone number in international format, for example +237600000001.</p>
      <form onSubmit={handleSubmit} className="form-stack">
        <input
          placeholder="Phone number"
          value={phone}
          onChange={(e) => setPhone(sanitizePhone(e.target.value))}
          autoComplete="tel"
          inputMode="tel"
          disabled={isSubmitting || Boolean(challengeId)}
        />
        {challengeId ? (
          <>
            <OtpInput value={code} onChange={setCode} length={4} disabled={isSubmitting} />
            <p>Code expires at {expiresLabel}.</p>
            <div className="button-row">
              <button className="primary-button" type="submit" disabled={isSubmitting || code.length < 4}>
                {isSubmitting ? 'Verifying...' : 'Verify code'}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={handleRequestOtp}
                disabled={isSubmitting || secondsLeft > 0}
              >
                {secondsLeft > 0 ? `Send a new code in ${secondsLeft}s` : 'Send a new code'}
              </button>
            </div>
          </>
        ) : (
          <button className="primary-button" type="submit" disabled={isSubmitting || !phone.trim()}>
            {isSubmitting ? 'Sending code...' : 'Send code'}
          </button>
        )}
      </form>
      {noticeMessage ? <p>{noticeMessage}</p> : null}
      {devCode ? (
        <p className="dev-otp">
          <strong>Development code: {devCode}</strong>
          <br />
          No SMS gateway is wired, so the server is showing you the code it
          would have sent. This does not exist outside development.
        </p>
      ) : null}
      {errorMessage ? <p>{errorMessage}</p> : null}
      <p>No account? <Link to="/signup">Sign up</Link></p>
    </main>
  );
}