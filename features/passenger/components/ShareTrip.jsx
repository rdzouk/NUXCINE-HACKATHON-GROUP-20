import { useState } from 'react';
import { revokeShare, shareRide } from '../services/ridesApi';

/**
 * Share the trip with somebody who has no account.
 *
 * The link is signed, expires, and can be killed before its signature lapses,
 * which is why revoking is offered next to it rather than buried. A share link
 * is precisely the sort of URL that gets forwarded onward, so being able to
 * take it back matters more than it looks.
 *
 * What the recipient sees is a deliberately thin view: where the car is, what
 * it looks like, and the driver's first name. Not the fare, not the
 * passenger's identity, and no phone number. Position stays coarse until the
 * trip is moving, so a link shared while waiting does not reveal which doorway
 * somebody is standing in.
 */
export default function ShareTrip({ rideId }) {
  const [link, setLink] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const create = async () => {
    setBusy(true);
    setErrorMessage('');
    try {
      const result = await shareRide(rideId);
      setLink(result.url);
      setExpiresAt(result.expires_at);
      setCopied(false);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setErrorMessage('');
    try {
      await revokeShare(rideId);
      setLink('');
      setExpiresAt('');
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // Clipboard access is refused in plenty of ordinary situations. The
      // link is on screen and selectable, so this is not worth an error.
      setCopied(false);
    }
  };

  return (
    <section className="share-trip">
      <h2>Share this trip</h2>

      {!link ? (
        <>
          <p className="section-note">
            Sends someone a live view of where you are. They see the car and
            the driver's first name, never your fare or either phone number.
          </p>
          <button
            className="secondary-button"
            type="button"
            onClick={create}
            disabled={busy}
          >
            {busy ? 'Creating link...' : 'Create a share link'}
          </button>
        </>
      ) : (
        <>
          <p className="share-trip__link">{link}</p>
          {expiresAt ? (
            <p className="section-note">
              Expires {new Date(expiresAt).toLocaleTimeString()}.
            </p>
          ) : null}
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={copy}>
              {copied ? 'Copied' : 'Copy link'}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={revoke}
              disabled={busy}
            >
              Stop sharing
            </button>
          </div>
        </>
      )}

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </section>
  );
}
