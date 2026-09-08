import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '../../map/services/apiClient';
import { getLocale } from '../../shared/services/locale';
import { speak, speechAvailable } from '../../shared/services/speech';

/**
 * What this passenger asked for, on the driver's screen, as instructions.
 *
 * Instructions rather than labels, and the difference matters at a kerb: a
 * driver reading "more legroom" has to work out what to do, while a driver
 * reading "move your seat forward before you arrive" already knows. The
 * wording comes from the API so it is written once and stays correctable.
 *
 * **What the driver never sees is why.** There is no diagnosis to show,
 * because none was ever recorded. A request for legroom looks identical
 * whether it came from somebody tall or somebody who uses a wheelchair, and
 * that is the design working rather than information being withheld (I9).
 *
 * **The spoken itinerary runs here, on the driver's phone.** That is the whole
 * point of it: a passenger who cannot see the route has no way to tell a
 * shortcut from a wrong turn unless it is said out loud, in the car, as it
 * happens. Announcing it on the passenger's own phone would help only a
 * passenger who could already read the screen.
 */
export default function RideInstructions({ ride }) {
  const [catalogue, setCatalogue] = useState([]);
  const locale = getLocale();
  const spokenSoFar = useRef(new Set());

  useEffect(() => {
    apiFetch('/ride-needs')
      .then((data) => setCatalogue(data.needs ?? []))
      .catch(() => setCatalogue([]));
  }, []);

  const needs = ride?.ride_needs ?? [];
  const note = ride?.ride_needs_note ?? '';

  const instructions = useMemo(() => {
    const wanted = new Set(needs);
    return catalogue
      .filter((n) => wanted.has(n.key))
      .map((n) => ({
        key: n.key,
        text: locale === 'en' ? n.driver_action_en : n.driver_action_fr,
      }));
  }, [catalogue, needs, locale]);

  const speaksItinerary = needs.includes('spoken_itinerary');

  // Announce each status change aloud when the passenger asked for it. Said
  // once per status: repeating "you are approaching the pickup" every socket
  // frame would make a driver turn it off, and then it helps nobody.
  useEffect(() => {
    if (!speaksItinerary || !speechAvailable()) return;
    if (!ride?.status) return;

    const key = `${ride.status}:${ride.dropoff?.label ?? ''}`;
    if (spokenSoFar.current.has(key)) return;
    spokenSoFar.current.add(key);

    const lines = {
      accepted:
        locale === 'en'
          ? `Heading to ${ride.pickup?.label ?? 'the pickup'}.`
          : `En route vers ${ride.pickup?.label ?? 'le point de depart'}.`,
      arrived:
        locale === 'en'
          ? 'You have arrived at the pickup. Ask the passenger for their code.'
          : 'Vous etes arrive. Demandez son code au passager.',
      in_progress:
        locale === 'en'
          ? `Trip started. Destination ${ride.dropoff?.label ?? ''}.`
          : `Course commencee. Destination ${ride.dropoff?.label ?? ''}.`,
      completed:
        locale === 'en' ? 'Trip complete.' : 'Course terminee.',
    };

    const line = lines[ride.status];
    if (line) speak(line, { locale });
  }, [ride?.status, ride?.pickup?.label, ride?.dropoff?.label, speaksItinerary, locale]);

  if (instructions.length === 0 && !note) return null;

  return (
    <section className="ride-panel">
      <p className="eyebrow">
        {locale === 'en' ? 'This passenger asked for' : 'Ce passager a demande'}
      </p>

      <ul className="driver-needs">
        {instructions.map((i) => (
          <li key={i.key}>{i.text}</li>
        ))}
      </ul>

      {note ? <p className="driver-needs__note">{note}</p> : null}

      {/* Not a repeat of the instruction above it. That one says what to do;
          this says where it happens, which is the part a driver would not
          guess: the announcement plays on their own handset, not on the
          passenger's, because a passenger who cannot see the route needs to
          hear it in the car. */}
      {speaksItinerary ? (
        <p className="section-note">
          {locale === 'en'
            ? 'This plays on your phone, not theirs. Turn the volume up before you set off.'
            : "Cela se joue sur votre telephone, pas sur le sien. Montez le volume avant de partir."}
        </p>
      ) : null}
    </section>
  );
}
