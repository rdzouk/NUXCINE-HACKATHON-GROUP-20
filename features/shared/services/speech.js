/**
 * Spoken ride updates, for passengers who cannot read the screen.
 *
 * The strings are **not written here**. The API already returns a spoken line
 * for each ride status in French and English, written to be heard rather than
 * read: short, front-loaded, free of the abbreviations a synthesiser mangles.
 * This file only speaks what the server sends, so a wording fix stays a server
 * change and the French is written once instead of in every client.
 *
 * The Web Speech API is built into the browser. No dependency, no bundle cost,
 * nothing to load on a slow connection. Where it is missing the app simply
 * stays silent and the screen still works, because speech is an addition here
 * and never the only way to learn something.
 *
 * **The PIN is spoken deliberately.** It is the one moment it is useful and
 * the passenger is about to read it aloud to the driver anyway. A blind
 * passenger who cannot see the PIN cannot use the anti-impersonation check at
 * all, which would make the safety feature sighted-only.
 */

const CANCEL_ON_NAVIGATE = true;

export function speechAvailable() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/**
 * Say one line.
 *
 * `interrupt` clears anything still queued. Ride updates supersede each other:
 * hearing "your driver is approaching" after they have already arrived is
 * worse than hearing nothing, so a newer line cancels an older one.
 */
export function speak(text, { locale = 'fr', interrupt = true } = {}) {
  if (!speechAvailable() || !text) return;

  try {
    if (interrupt && CANCEL_ON_NAVIGATE) {
      window.speechSynthesis.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = locale === 'en' ? 'en-GB' : 'fr-FR';
    // Slightly under default. Synthesised French at full rate is hard to
    // follow, and this is often heard once, outdoors, next to traffic.
    utterance.rate = 0.95;
    utterance.pitch = 1;

    window.speechSynthesis.speak(utterance);
  } catch {
    // A browser that refuses to speak must never break the screen.
  }
}

export function stopSpeaking() {
  if (speechAvailable()) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* nothing to do */
    }
  }
}

const STORAGE_KEY = 'vora.speech.enabled';

/**
 * Whether the passenger has asked for spoken updates.
 *
 * Off by default, and that is deliberate rather than lazy: a phone that starts
 * talking unprompted in a shared taxi announces to everyone around you that
 * you need it to. Turning it on is the passenger's choice, and it persists.
 */
export function speechEnabled() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function setSpeechEnabled(enabled) {
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
  } catch {
    /* private mode; the setting simply does not persist */
  }
  if (!enabled) stopSpeaking();
}
