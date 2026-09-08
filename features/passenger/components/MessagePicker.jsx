import { useState } from 'react';
import { sendRideMessage } from '../services/ridesApi';

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
  { key: 'at_gate', label: 'I am at the gate' },
  { key: 'two_min', label: 'Two minutes away' },
  { key: 'cant_find_you', label: 'I cannot find you' },
  { key: 'please_wait_5', label: 'Please wait five minutes' },
];

export default function MessagePicker({ rideId }) {
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
      <h2>Message your driver</h2>
      <p className="section-note">
        Fixed messages only. We never share either phone number.
      </p>

      <div className="message-picker__options">
        {TEMPLATES.map((t) => (
          <button
            key={t.key}
            type="button"
            className="secondary-button"
            disabled={sending === t.key}
            onClick={() => send(t.key, t.label)}
          >
            {sending === t.key ? 'Sending...' : t.label}
          </button>
        ))}
      </div>

      {sent ? <p className="form-notice">Sent: {sent}</p> : null}
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </section>
  );
}
