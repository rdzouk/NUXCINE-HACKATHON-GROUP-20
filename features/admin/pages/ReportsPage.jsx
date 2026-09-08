import NotBuilt from '../components/NotBuilt';
import { getLocale } from '../../shared/services/locale';

/**
 * Incidents and SOS events exist in the database. They are deliberately not
 * readable here.
 *
 * `POST /rides/{id}/sos` seals an immutable snapshot enforced by a trigger,
 * and `POST /rides/{id}/report` files an incident. Both are written. Exposing
 * them to an admin console is a separate decision: an SOS record is the most
 * sensitive row in the system, and a console that reads them needs an access
 * log of its own before it needs a table layout.
 */
export default function ReportsPage() {
  const en = getLocale() === 'en';

  return (
    <NotBuilt
      title={en ? 'Reports and incidents' : 'Signalements et incidents'}
      endpoint="GET /admin/incidents"
      note={
        en
          ? 'SOS and incident records are written and sealed by the API. Reading them from a console is a separate decision that needs its own access log, so the screen is empty rather than showing rows that were never fetched.'
          : "Les enregistrements SOS et incidents sont ecrits et scelles par l'API. Les lire depuis une console est une decision distincte qui exige son propre journal d'acces, donc l'ecran est vide plutot que de montrer des lignes jamais recuperees."
      }
    />
  );
}
