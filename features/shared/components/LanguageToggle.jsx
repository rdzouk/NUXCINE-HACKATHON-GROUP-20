import { useEffect, useState } from 'react';
import { getLocale, onLocaleChange, setLocale } from '../services/locale';

/**
 * FR / EN, switching the whole app at once.
 *
 * Both halves move together: the client re-renders from its own strings and
 * every subsequent request carries the new `Accept-Language`, so server
 * errors, ride announcements and the needs vocabulary follow. Before this, an
 * English screen could answer in French, which reads as a bug rather than as
 * bilingualism.
 *
 * A full reload rather than a re-render. Strings are read at render time
 * throughout the app, and a reload is one line that is certainly correct,
 * where threading a context through 32 screens at this stage would be a lot
 * of edits for the same result.
 */
export default function LanguageToggle() {
  const [locale, setCurrent] = useState(getLocale);

  useEffect(() => onLocaleChange(setCurrent), []);

  const choose = (next) => {
    if (next === locale) return;
    setLocale(next);
    window.location.reload();
  };

  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      {['fr', 'en'].map((code) => (
        <button
          key={code}
          type="button"
          className={code === locale ? 'is-selected' : ''}
          aria-pressed={code === locale}
          onClick={() => choose(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
