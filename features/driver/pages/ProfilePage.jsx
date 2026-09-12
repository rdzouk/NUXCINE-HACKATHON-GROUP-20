import { useEffect, useState } from 'react';
import DriverNav from '../components/DriverNav';
import PageHeader from '../../shared/components/PageHeader';
import LanguageToggle from '../../shared/components/LanguageToggle';
import { getMe } from '../../shared/services/profileApi';
import { clearSession } from '../../auth/services/session';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

/**
 * The driver's own profile, from `GET /me`.
 *
 * This was five hardcoded lines: a driver called Jean, a grey Corolla with
 * plate LT 1234 AB, a 4.9 rating and an "Edit profile" button that did
 * nothing. Every one of those was invented, on the one screen whose entire
 * purpose is to show a person their own record.
 *
 * **The rating is shown only when the server sends one.** `rating_avg` is
 * null until ratings exist, and there is no endpoint that collects them yet,
 * so this renders nothing rather than a flattering number.
 *
 * The sign-out control is here because it was nowhere. A driver could reach
 * this screen and had no way to leave the account, which also made it
 * impossible to demonstrate both sides of a ride from one machine.
 */
export default function ProfilePage() {
  const en = getLocale() === 'en';
  const [user, setUser] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    getMe()
      .then((me) => setUser(me.user ?? me))
      .catch((error) => setErrorMessage(error.message));
  }, []);

  const driver = user?.driver;

  const kycLabel = (status) => {
    const labels = {
      en: {
        pending: 'awaiting review',
        verified: 'verified',
        rejected: 'rejected',
        suspended: 'suspended',
      },
      fr: {
        pending: 'en attente',
        verified: 'verifie',
        rejected: 'rejete',
        suspended: 'suspendu',
      },
    };
    return labels[en ? 'en' : 'fr'][status] ?? status;
  };

  return (
    <main className="app-shell">
      <PageHeader
        title={t('common.profile')}
        fallback="/driver/dashboard"
        right={<LanguageToggle />}
      />

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      {user === null && !errorMessage ? (
        <p className="section-note">{t('common.loading')}</p>
      ) : null}

      {user ? (
        <>
          <p className="eyebrow">{en ? 'Account' : 'Compte'}</p>

          <div className="fact-row">
            <span>{en ? 'Name' : 'Nom'}</span>
            <strong>{user.display_name}</strong>
          </div>
          <div className="fact-row">
            <span>{en ? 'Phone' : 'Telephone'}</span>
            <strong>{user.phone_e164}</strong>
          </div>

          {driver ? (
            <>
              <div className="fact-row">
                <span>KYC</span>
                <strong>{kycLabel(driver.kyc_status)}</strong>
              </div>
              <div className="fact-row">
                <span>{en ? 'Duty' : 'Service'}</span>
                <strong>
                  {driver.is_online
                    ? en ? 'On duty' : 'En service'
                    : en ? 'Off duty' : 'Hors service'}
                </strong>
              </div>
              {/* Only when the server has one. There is no endpoint that
                  collects ratings yet, so this stays absent rather than
                  showing a number nobody earned. */}
              {driver.rating_avg != null ? (
                <div className="fact-row">
                  <span>{en ? 'Rating' : 'Note'}</span>
                  <strong>{driver.rating_avg.toFixed(1)} / 5</strong>
                </div>
              ) : null}
            </>
          ) : null}

          <p className="section-note">
            {en
              ? 'Vehicle details are held against your KYC record and are changed by an administrator, not here.'
              : "Les informations du vehicule sont rattachees a votre dossier KYC et sont modifiees par un administrateur, pas ici."}
          </p>

          <div className="button-row">
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                clearSession();
                window.location.assign('/login');
              }}
            >
              {t('common.logout')}
            </button>
          </div>
        </>
      ) : null}

      <DriverNav />
    </main>
  );
}
