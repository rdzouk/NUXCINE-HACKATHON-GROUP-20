import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { peekOtp, requestOtp, verifyOtp } from '../services/authApi';
import { getAccessToken, getRouteForRole, getStoredUser } from '../services/session';
import { t } from '../../shared/services/strings';

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
      <h1>{t('auth.signupTitle')}</h1>
      <p>{t('auth.signupHint')}</p>
      <form onSubmit={handleSubmit} className="form-stack">
        <input
          placeholder={t('auth.phone')}
          value={phone}
          onChange={(e) => setPhone(sanitizePhone(e.target.value))}
          autoComplete="tel"
          inputMode="tel"
          disabled={isSubmitting || Boolean(challengeId)}
        />
        {challengeId ? (
          <>
            <input
              placeholder={t('auth.code')}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
              autoComplete="one-time-code"
              inputMode="numeric"
              disabled={isSubmitting}
            />
            <p>{t('auth.expires')} {expiresLabel}.</p>
            <div className="button-row">
              <button className="primary-button" type="submit" disabled={isSubmitting || code.trim().length < 4}>
                {isSubmitting ? t('auth.verifying') : t('auth.verify')}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={handleRequestOtp}
                disabled={isSubmitting}
              >
                {t('auth.resend')}
              </button>
            </div>
          </>
        ) : (
          <button className="primary-button" type="submit" disabled={isSubmitting || !phone.trim()}>
            {isSubmitting ? t('auth.sending') : t('auth.send')}
          </button>
        )}
      </form>
      {noticeMessage ? <p>{noticeMessage}</p> : null}
      {devCode ? (
        <p className="dev-otp">
          <strong>{t('auth.devCode')} {devCode}</strong>
          <br />
          {t('auth.devNote')}
        </p>
      ) : null}
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      <p>{t('auth.haveAccount')} <Link to="/login">{t('auth.login')}</Link></p>
    </main>
  );
}