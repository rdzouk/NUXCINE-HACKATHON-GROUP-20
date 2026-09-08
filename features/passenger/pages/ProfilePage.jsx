import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import LanguageToggle from '../../shared/components/LanguageToggle';
import { getMe, getVehicleCapabilities, updateMe } from '../../shared/services/profileApi';
import { clearSession } from '../../auth/services/session';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

/**
 * The profile field each capability maps to.
 *
 * Every one of these is a fact about a **vehicle**, never about the person.
 * That is a legal requirement, not a wording preference: Law No. 2024/017
 * prohibits processing health data, and "this passenger uses a wheelchair" is
 * health data while "this trip needs a ramp" is a logistics requirement (I9).
 *
 * So the section is called "Vehicle needs" and every label describes a car.
 * Nothing here may drift toward describing a condition.
 */
const CAPABILITY_FIELDS = {
  ramp: 'requires_ramp',
  boot_space: 'requires_boot_space',
  front_seat: 'requires_front_seat',
  driver_assist: 'requires_driver_assist',
  guide_animal: 'allows_guide_animal',
  extra_legroom: 'requires_extra_legroom',
};

export default function ProfilePage() {
  const locale = getLocale();
  const [user, setUser] = useState(null);
  const [capabilities, setCapabilities] = useState([]);
  const [saving, setSaving] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    Promise.all([getMe(), getVehicleCapabilities()])
      .then(([me, caps]) => {
        setUser(me.user ?? me);
        setCapabilities(caps.capabilities ?? []);
      })
      .catch((error) => setErrorMessage(error.message));
  }, []);

  const toggle = async (field, next) => {
    setSaving(field);
    setErrorMessage('');

    const current = user.accessibility ?? {};
    const nextAccessibility = { ...current, [field]: next };

    // Optimistic, because a switch that lags behind the finger feels broken.
    setUser((prev) => ({ ...prev, accessibility: nextAccessibility }));

    try {
      // PATCH takes the whole accessibility object, not a single field, so
      // send the merged version. Sending one key would clear the rest.
      const updated = await updateMe({ accessibility: nextAccessibility });
      setUser(updated.user ?? updated);
    } catch (error) {
      setUser((prev) => ({ ...prev, accessibility: current }));
      setErrorMessage(error.message);
    } finally {
      setSaving('');
    }
  };

  if (!user) {
    return (
      <main className="app-shell">
        <h1>{t('common.profile')}</h1>
        <p>{errorMessage || 'Loading...'}</p>
        <BottomNav />
      </main>
    );
  }

  return (
    <main className="app-shell">
      <h1>{t('common.profile')}</h1>

      <p><strong>{locale === 'en' ? 'Name' : 'Nom'}:</strong>{' '}
        {user.display_name ?? (locale === 'en' ? 'Not set' : 'Non defini')}</p>
      <p><strong>{locale === 'en' ? 'Phone' : 'Telephone'}:</strong>{' '}
        {user.phone_e164 ?? user.phone}</p>

      <div className="profile-row">
        <span>{t('common.language')}</span>
        <LanguageToggle />
      </div>

      <h2>{locale === 'en' ? 'Vehicle needs' : 'Besoins du vehicule'}</h2>
      <p className="section-note">
        {locale === 'en'
          ? 'These describe the vehicle sent to you, so we only offer rides in cars that can carry you. We store nothing about you, only what the car needs to have.'
          : "Ceci decrit le vehicule qui vous est envoye, afin de ne proposer que des voitures adaptees. Nous n'enregistrons rien sur vous, seulement ce que la voiture doit avoir."}
      </p>

      <ul className="toggle-list">
        {capabilities.map((cap) => {
          const field = CAPABILITY_FIELDS[cap.key];
          if (!field) return null;

          return (
            <li key={cap.key}>
              <label>
                <input
                  type="checkbox"
                  checked={Boolean(user.accessibility?.[field])}
                  disabled={saving === field}
                  onChange={(e) => toggle(field, e.target.checked)}
                />
                <span>
                  <span className="toggle-list__name">
                    {locale === 'en' ? cap.label_en : cap.label_fr}
                  </span>
                  <span className="toggle-list__note">
                    {locale === 'en' ? cap.description_en : cap.description_fr}
                  </span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>

      <h2>{locale === 'en' ? 'During the ride' : 'Pendant le trajet'}</h2>
      <ul className="toggle-list">
        <li>
          <label>
            <input
              type="checkbox"
              checked={Boolean(user.accessibility?.prefers_quiet_ride)}
              disabled={saving === 'prefers_quiet_ride'}
              onChange={(e) => toggle('prefers_quiet_ride', e.target.checked)}
            />
            <span>
              <span className="toggle-list__name">
                {locale === 'en' ? 'Quiet ride' : 'Trajet silencieux'}
              </span>
              {/* No reason is asked for and none is stored. A migraine, an
                  interview to prepare for, exhaustion, or simply not wanting
                  to talk are all the same request as far as the system is
                  concerned, and none of them are its business. */}
              <span className="toggle-list__note">
                Your driver is asked to keep conversation to what the trip
                needs: confirming the pickup, and telling you when you have
                arrived. You never have to explain why.
              </span>
            </span>
          </label>
        </li>
        <li>
          <label>
            <input
              type="checkbox"
              checked={Boolean(user.accessibility?.prefers_text_contact)}
              disabled={saving === 'prefers_text_contact'}
              onChange={(e) => toggle('prefers_text_contact', e.target.checked)}
            />
            <span>
              <span className="toggle-list__name">
                {locale === 'en' ? 'Prefer written messages' : 'Preferer les messages ecrits'}
              </span>
              {/* Deliberately not a vehicle capability, so it does not narrow
                  the driver pool. It changes how a driver is asked to reach
                  you, nothing else. */}
              <span className="toggle-list__note">
                Drivers are asked to message rather than call. This does not
                affect which vehicles are offered to you.
              </span>
            </span>
          </label>
        </li>
      </ul>

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

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

      <div className="legal-links">
        <Link to="/legal/privacy">
          {locale === 'en' ? 'Privacy policy' : 'Confidentialite'}
        </Link>
        <Link to="/legal/terms">
          {locale === 'en' ? 'Terms and conditions' : 'Conditions generales'}
        </Link>
      </div>

      <BottomNav />
    </main>
  );
}
