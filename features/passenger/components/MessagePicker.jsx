import { useState } from 'react';
import { sendRideMessage } from '../services/ridesApi';
import { getLocale } from '../../shared/services/locale';

/**
 * The four things a passenger actually needs to say at a kerb.
 *
 * A closed set, not a text box. This replaces exchanging phone numbers, so it
 * has to do the job of a phone call without becoming a channel for harassment:
 * a fixed template cannot carry abuse, cannot carry an off-app number, and
 * cannot leak an identity. It also sends a few bytes, which matters on the
 * network this is built for.
 *
 * The keys come from the contract's MessageTemplate enum. The server renders
 * the wording in the recipient's own language, so what is written here is the
 * label on the button, not the message that arrives.
 */
const TEMPLATES = [
  { key: 'at_gate', en: 'I am at the gate', fr: 'Je suis au portail' },
  { key: 'two_min', en: 'Two minutes away', fr: 'Deux minutes' },
  { key: 'cant_find_you', en: 'I cannot find you', fr: 'Je ne vous trouve pas' },
  { key: 'please_wait_5', en: 'Please wait five minutes', fr: 'Attendez cinq minutes' },
];

export default function MessagePicker({ rideId }) {
  const en = getLocale() === 'en';
  const [sending, setSending] = useState('');
  const [sent, setSent] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const send = async (key, label) => {
    setSending(key);
    setErrorMessage('');
    try {
      await sendRideMessage(rideId, key);
      setSent(label);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setSending('');
    }
  };

  return (
    <section className="message-picker">
      <h2>{en ? 'Message your driver' : 'Ecrire au chauffeur'}</h2>
      <p className="section-note">
        {en
          ? 'Fixed messages only. We never share either phone number.'
          : "Messages predefinis uniquement. Aucun numero de telephone n'est jamais partage."}
      </p>

      <div className="message-picker__options">
        {TEMPLATES.map((template) => (
          <button
            key={template.key}
            type="button"
            className="secondary-button"
            disabled={sending === template.key}
            onClick={() => send(template.key, en ? template.en : template.fr)}
          >
            {sending === template.key
              ? en ? 'Sending...' : 'Envoi...'
              : en ? template.en : template.fr}
          </button>
        ))}
      </div>

      {sent ? (
        <p className="form-notice">
          {en ? 'Sent' : 'Envoye'}: {sent}
        </p>
      ) : null}
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </section>
  );
}
