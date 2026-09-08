import { useEffect, useRef, useState } from 'react';
import {
  setSpeechEnabled,
  speak,
  speechAvailable,
  speechEnabled,
  stopSpeaking,
} from '../services/speech';
import { t } from '../services/strings';

/**
 * Spoken ride updates, and the switch that turns them on.
 *
 * Speaks `ride.announcement`, which the server writes. Nothing is composed
 * here, so the wording stays correctable without an app release and the French
 * is written once.
 *
 * **Only when the line changes.** A socket delivers the ride repeatedly, and
 * re-reading "your driver is approaching" every few seconds would be unusable
 * rather than helpful. The last spoken line is remembered and repeats are
 * dropped.
 *
 * **Off unless asked for.** A phone that starts talking by itself in a shared
 * taxi tells everyone nearby that you need it to. That is the passenger's
 * information to give out, not ours, so the default is silence and the choice
 * persists.
 *
 * Renders nothing where the browser has no speech support, rather than showing
 * a switch that does nothing.
 */
export default function VoiceGuide({ announcement, locale = 'fr' }) {
  const [enabled, setEnabled] = useState(speechEnabled);
  const lastSpoken = useRef('');

  useEffect(() => {
    if (!enabled || !announcement) return;
    if (announcement === lastSpoken.current) return;

    lastSpoken.current = announcement;
    speak(announcement, { locale });
  }, [announcement, enabled, locale]);

  // Stop mid-sentence when the screen goes away. A voice that keeps narrating
  // a ride the passenger has left is worse than one that says nothing.
  useEffect(() => () => stopSpeaking(), []);

  if (!speechAvailable()) return null;

  const toggle = () => {
    const next = !enabled;
    setEnabled(next);
    setSpeechEnabled(next);

    // Say the current line immediately on turning it on, so the switch
    // demonstrably did something.
    if (next && announcement) {
      lastSpoken.current = announcement;
      speak(announcement, { locale });
    }
  };

  return (
    <button
      type="button"
      className={enabled ? 'voice-guide is-on' : 'voice-guide'}
      onClick={toggle}
      aria-pressed={enabled}
    >
      <span className="voice-guide__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M11 5 6 9H3v6h3l5 4V5Z"
            fill="currentColor"
          />
          {enabled ? (
            <>
              <path
                d="M15.5 8.5a5 5 0 0 1 0 7"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M18.5 5.5a9 9 0 0 1 0 13"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </>
          ) : (
            <path
              d="m16 9 5 6m0-6-5 6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          )}
        </svg>
      </span>
      <span>{enabled ? t('ride.speaking') : t('ride.speak')}</span>
    </button>
  );
}
