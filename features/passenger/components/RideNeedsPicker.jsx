import { useEffect, useState } from 'react';
import { apiFetch } from '../../map/services/apiClient';
import { getLocale } from '../../shared/services/locale';
import { t } from '../../shared/services/strings';

/**
 * What the passenger needs on this ride.
 *
 * **Needs, never diagnoses.** Every option describes something the driver
 * does. Nothing here records anything about the person choosing it, and the
 * system deliberately cannot tell why any of them was picked: somebody tall,
 * somebody who gets carsick and somebody with a mobility impairment select the
 * same thing. Law 2024/017 prohibits processing health data, and this is what
 * staying the right side of it looks like on a screen (I9).
 *
 * The list and its wording come from the API rather than being written here,
 * so a phrasing correction is a server change and the French is written once.
 *
 * Options marked `requires_undertaking` are things a driver does rather than
 * things a car has, so choosing one restricts the ride to drivers who have
 * signed the undertakings. That is said plainly rather than hidden, because a
 * passenger should know why a request might mean a slightly longer wait.
 */
export default function RideNeedsPicker({ value = [], note = '', onChange }) {
  const [needs, setNeeds] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const locale = getLocale();

  useEffect(() => {
    apiFetch('/ride-needs')
      .then((data) => setNeeds(data.needs ?? []))
      .catch(() => setNeeds([]));
  }, []);

  if (needs.length === 0) return null;

  const toggle = (key) => {
    const next = value.includes(key)
      ? value.filter((k) => k !== key)
      : [...value, key];
    onChange(next, key === 'other' && !next.includes('other') ? '' : note);
  };

  const label = (n) => (locale === 'en' ? n.label_en : n.label_fr);
  const action = (n) => (locale === 'en' ? n.driver_action_en : n.driver_action_fr);

  return (
    <section className="needs-picker">
      <button
        type="button"
        className="needs-picker__summary"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span>
          <span className="needs-picker__title">{t('book.needs')}</span>
          <span className="needs-picker__count">
            {value.length > 0
              ? value.map((k) => label(needs.find((n) => n.key === k) ?? {})).join(', ')
              : locale === 'en'
                ? 'Nothing selected'
                : 'Rien de selectionne'}
          </span>
        </span>
        <span className={expanded ? 'needs-picker__chevron is-open' : 'needs-picker__chevron'}>
          &#8250;
        </span>
      </button>

      {expanded ? (
        <>
          <p className="section-note">{t('book.needsNote')}</p>

          <ul className="toggle-list">
            {needs.map((n) => (
              <li key={n.key}>
                <label>
                  <input
                    type="checkbox"
                    checked={value.includes(n.key)}
                    onChange={() => toggle(n.key)}
                  />
                  <span>
                    <span className="toggle-list__name">{label(n)}</span>
                    <span className="toggle-list__note">{action(n)}</span>
                    {n.requires_undertaking ? (
                      <span className="needs-picker__gate">
                        {locale === 'en'
                          ? 'Only drivers who have signed the service undertakings'
                          : 'Uniquement les chauffeurs ayant signe les engagements'}
                      </span>
                    ) : null}
                  </span>
                </label>
              </li>
            ))}
          </ul>

          {value.includes('other') ? (
            <input
              className="needs-picker__note"
              value={note}
              maxLength={140}
              placeholder={t('book.needsOther')}
              onChange={(e) => onChange(value, e.target.value)}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
