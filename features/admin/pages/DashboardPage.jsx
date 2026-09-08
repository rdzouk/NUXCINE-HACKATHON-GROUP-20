import { useEffect, useState } from 'react';
import Sidebar from '../components/Sidebar';
import { apiFetch } from '../../map/services/apiClient';
import { getLocale } from '../../shared/services/locale';

/**
 * Admin overview, on real numbers.
 *
 * It was three hardcoded figures, which is worse than an empty screen: a
 * dashboard showing 142 users on a database holding five is a screen nobody
 * can trust, and a reader who catches one invented number stops believing the
 * rest of them.
 *
 * `GET /admin/drivers` returns a bare array and only answers when asked for a
 * specific `kyc_status`, so both states are fetched and combined here.
 *
 * **A failed call is shown, not swallowed.** The first version caught each
 * request and substituted an empty list, so a passenger who opened this URL
 * saw three confident zeros. Zero drivers online is a claim about the fleet;
 * "you are not an administrator" is the truth, and the two must not look
 * alike.
 *
 * What is not built says so. The admin surface was scoped to the six endpoints
 * Phase 1 and Phase 5 already needed, and only two exist.
 */
// The API speaks the enum; the screen should speak French when the app does.
const KYC_LABELS = {
  en: { pending: "awaiting review", verified: "verified", rejected: "rejected", suspended: "suspended" },
  fr: { pending: "en attente", verified: "verifie", rejected: "rejete", suspended: "suspendu" },
};

function kycLabel(status, en) {
  return KYC_LABELS[en ? "en" : "fr"][status] ?? status;
}

export default function DashboardPage() {
  const en = getLocale() === 'en';
  const [drivers, setDrivers] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    Promise.all([
      apiFetch('/admin/drivers?kyc_status=verified'),
      apiFetch('/admin/drivers?kyc_status=pending'),
    ])
      .then(([verified, pending]) =>
        setDrivers([...(verified ?? []), ...(pending ?? [])]),
      )
      .catch((error) => setErrorMessage(error.message));
  }, []);

  const verified = drivers?.filter((d) => d.kyc_status === 'verified') ?? [];
  const pending = drivers?.filter((d) => d.kyc_status === 'pending') ?? [];
  const online = drivers?.filter((d) => d.is_online) ?? [];

  return (
    <div className="admin-layout">
      <Sidebar />

      <main className="app-shell">
        <p className="eyebrow">{en ? 'Operations' : 'Exploitation'}</p>
        <h1 className="headline">{en ? 'Overview' : 'Synthese'}</h1>

        {errorMessage ? (
          <>
            <p className="form-error">{errorMessage}</p>
            <p className="section-note">
              {en
                ? 'This screen needs an administrator account. Sign in with the admin demo number in the README.'
                : "Cet ecran demande un compte administrateur. Connectez-vous avec le numero admin de demonstration indique dans le README."}
            </p>
          </>
        ) : drivers === null ? (
          <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
        ) : (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <p className="stat-value">{online.length}</p>
                <p className="stat-label">
                  {en ? 'Drivers online' : 'Chauffeurs en ligne'}
                </p>
              </div>
              <div className="stat-card">
                <p className="stat-value">{verified.length}</p>
                <p className="stat-label">{en ? 'Verified' : 'Verifies'}</p>
              </div>
              <div className="stat-card">
                <p className="stat-value">{pending.length}</p>
                <p className="stat-label">
                  {en ? 'Awaiting KYC' : 'En attente de KYC'}
                </p>
              </div>
            </div>

            <p className="eyebrow">{en ? 'Fleet' : 'Flotte'}</p>

            {drivers.length === 0 ? (
              <p className="section-note">
                {en
                  ? 'No drivers registered yet.'
                  : 'Aucun chauffeur enregistre pour le moment.'}
              </p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{en ? 'Driver' : 'Chauffeur'}</th>
                    <th>KYC</th>
                    <th>Documents</th>
                    <th>{en ? 'Status' : 'Statut'}</th>
                  </tr>
                </thead>
                <tbody>
                  {drivers.slice(0, 14).map((d) => (
                    <tr key={d.driver_id}>
                      <td>{d.display_name ?? d.driver_id.slice(0, 8)}</td>
                      <td>{kycLabel(d.kyc_status, en)}</td>
                      <td>
                        {d.missing?.length
                          ? `${d.missing.length} ${en ? 'missing' : 'manquant(s)'}`
                          : `${d.submitted?.length ?? 0} ${en ? 'on file' : 'au dossier'}`}
                      </td>
                      <td>
                        {d.is_online
                          ? en ? 'Online' : 'En ligne'
                          : en ? 'Offline' : 'Hors ligne'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Said rather than faked. */}
            <p className="section-note">
              {en
                ? 'Ride volume, revenue and incident reporting are not built. The admin surface was scoped to the six endpoints Phase 1 and Phase 5 already needed, and only the driver list and the KYC decision exist so far.'
                : "Le volume de courses, les revenus et le suivi des incidents ne sont pas construits. La surface admin a ete limitee aux six endpoints dont les phases 1 et 5 avaient besoin, et seuls la liste des chauffeurs et la decision KYC existent."}
            </p>
          </>
        )}
      </main>
    </div>
  );
}
