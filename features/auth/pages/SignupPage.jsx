import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { peekOtp, requestOtp, verifyOtp } from '../services/authApi';
import { getAccessToken, getRouteForRole, getStoredUser } from '../services/session';

function sanitizePhone(value) {
  const trimmed = value.trim();

  if (trimmed.startsWith('+')) {
    return `+${trimmed.slice(1).replace(/\D/g, '')}`;
  }

  return trimmed.replace(/\D/g, '');
}

export default function SignupPage() {
  const [phone, setPhone] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [code, setCode] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [resendAfterSeconds, setResendAfterSeconds] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [noticeMessage, setNoticeMessage] = useState('');
  const [devCode, setDevCode] = useState('');
  const navigate = useNavigate();

  const expiresLabel = useMemo(() => {
    if (!expiresAt) {
      return '';
    }

    return new Date(expiresAt).toLocaleTimeString();
  }, [expiresAt]);

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
      setCode('');
      setNoticeMessage('Verify this code to create your account and open a session.');

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
      <h1>Create account</h1>
      <p>Accounts are created after phone verification. Use international format, for example +237600000001.</p>
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
            <input
              placeholder="OTP code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
              autoComplete="one-time-code"
              inputMode="numeric"
              disabled={isSubmitting}
            />
            <p>
              Code expires at {expiresLabel}.
              {typeof resendAfterSeconds === 'number' ? ` You can request another code after ${resendAfterSeconds} seconds.` : ''}
            </p>
            <div className="button-row">
              <button className="primary-button" type="submit" disabled={isSubmitting || code.trim().length < 4}>
                {isSubmitting ? 'Creating account...' : 'Verify and continue'}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={handleRequestOtp}
                disabled={isSubmitting}
              >
                Send a new code
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
      <p>Already have an account? <Link to="/login">Log in</Link></p>
    </main>
  );
}