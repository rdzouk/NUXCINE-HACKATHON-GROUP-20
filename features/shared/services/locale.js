/**
 * One language for the whole app, client and server.
 *
 * The bug this fixes: the interface was written in English while the API
 * negotiated French from the browser's own `Accept-Language`, so an English
 * form answered an English button with "Trop de tentatives." Two halves of one
 * screen disagreeing about the language is worse than either language alone,
 * because it reads as broken rather than as foreign.
 *
 * So the choice lives here, the client renders in it, and every request
 * carries it as `Accept-Language`. The server's i18n already speaks both, so
 * one setting moves both halves together.
 *
 * French is the default. This is built for Cameroon, where it is the language
 * of the street the app describes, and defaulting to English because the
 * developers wrote English would be the wrong way round.
 */

const KEY = 'vora.locale';
export const LOCALES = ['fr', 'en'];
const DEFAULT = 'fr';

let current = null;
const listeners = new Set();

export function getLocale() {
  if (current) return current;

  try {
    const stored = window.localStorage.getItem(KEY);
    if (LOCALES.includes(stored)) {
      current = stored;
      return current;
    }
  } catch {
    /* private mode */
  }

  current = DEFAULT;
  return current;
}

export function setLocale(next) {
  if (!LOCALES.includes(next)) return;

  current = next;
  try {
    window.localStorage.setItem(KEY, next);
  } catch {
    /* the setting simply does not persist */
  }

  if (typeof document !== 'undefined') {
    document.documentElement.lang = next;
  }

  listeners.forEach((fn) => fn(next));
}

/** Subscribe to changes, so a switch re-renders everything at once. */
export function onLocaleChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
