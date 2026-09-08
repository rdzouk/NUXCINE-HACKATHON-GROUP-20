import Sidebar from './Sidebar';
import { getLocale } from '../../shared/services/locale';

/**
 * A screen that says what is missing instead of inventing it.
 *
 * These four admin pages rendered tables of fabricated rows: two invented
 * users, two invented rides, one invented SOS report, all presented exactly
 * as the real dashboard presents real ones. A reader has no way to tell which
 * screen is which, so the fake rows do not just fail to inform, they make the
 * true screens harder to believe.
 *
 * The hackathon brief bans it outright ("utiliser de fausses donnees en les
 * presentant comme reelles"), and it would have been the wrong call anyway.
 * An empty screen that names the missing endpoint is a smaller claim and a
 * more useful one: it tells you exactly what would have to be built next.
 */
export default function NotBuilt({ title, endpoint, note }) {
  const en = getLocale() === 'en';

  return (
    <div className="admin-layout">
      <Sidebar />

      <main className="app-shell">
        <p className="eyebrow">{en ? 'Operations' : 'Exploitation'}</p>
        <h1 className="headline">{title}</h1>

        <p className="section-note">
          {en
            ? 'This screen is not built. The admin surface was scoped to the endpoints Phase 1 and Phase 5 needed, and this is not one of them.'
            : "Cet ecran n'est pas construit. La surface admin a ete limitee aux endpoints dont les phases 1 et 5 avaient besoin, et celui-ci n'en fait pas partie."}
        </p>

        <p className="eyebrow">{en ? 'What it would need' : "Ce qu'il faudrait"}</p>
        <p className="section-note">
          <code>{endpoint}</code>
        </p>

        {note ? <p className="section-note">{note}</p> : null}
      </main>
    </div>
  );
}
