import { useCallback, useEffect, useState } from 'react';
import Sidebar from '../components/Sidebar';
import { apiFetch } from '../../map/services/apiClient';
import { getLocale } from '../../shared/services/locale';

/**
 * The KYC review queue, on real drivers, with the decision wired.
 *
 * This was a table of two invented drivers from a mock context. It is the one
 * admin capability the backend actually has, so faking it was the worst place
 * to fake anything: a working feature was being represented by a fake version
 * of itself.
 *
 * `GET /admin/drivers` answers one `kyc_status` at a time, so the tabs below
 * are the query rather than a client-side filter.
 *
 * **Approving is refused while a required document is missing**, and that rule
 * lives in the service, not here. This screen can show the reason but cannot
 * grant an exception, which is the point: a second interface that could
 * override the check would make the check worthless.
 *
 * No phone number and no document contents come back from this endpoint. An
 * admin approving KYC needs to know which documents exist, not what they say,
 * so a compromised admin session leaks neither.
 */

const TABS = ['pending', 'verified', 'rejected'];

// The API speaks the enum; the screen should speak French when the app does.
const KYC_LABELS = {
  en: { pending: "awaiting review", verified: "verified", rejected: "rejected", suspended: "suspended" },
  fr: { pending: "en attente", verified: "verifie", rejected: "rejete", suspended: "suspendu" },
};

function kycLabel(status, en) {
  return KYC_LABELS[en ? "en" : "fr"][status] ?? status;
}

export default function DriversPage() {
  const en = getLocale() === 'en';
  const [tab, setTab] = useState('pending');
  const [rows, setRows] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async (status) => {
    setRows(null);
    setErrorMessage('');
    try {
      const data = await apiFetch(`/admin/drivers?kyc_status=${status}`);
      setRows(data ?? []);
    } catch (error) {
      setErrorMessage(error.message);
      setRows([]);
    }
  }, []);

  useEffect(() => {
    load(tab);
  }, [load, tab]);

  const decide = async (driver, status) => {
    // A rejection without a reason is refused by the API, deliberately: the
    // driver has to be able to correct the thing and resubmit. Asking here
    // rather than sending a request we know will fail.
    let reason = null;
    if (status === 'rejected') {
      reason = window.prompt(
        en ? 'Reason for rejection' : 'Motif du rejet',
        en ? 'Document unreadable' : 'Document illisible',
      );
      if (!reason) return;
    }

    setBusyId(driver.driver_id);
    setErrorMessage('');
    try {
      await apiFetch(`/admin/drivers/${driver.driver_id}/kyc`, {
        method: 'POST',
        body: JSON.stringify({ status, reason }),
      });
      await load(tab);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setBusyId(null);
    }
  };

  const label = {
    pending: en ? 'Awaiting review' : 'En attente',
    verified: en ? 'Verified' : 'Verifies',
    rejected: en ? 'Rejected' : 'Rejetes',
  };

  return (
    <div className="admin-layout">
      <Sidebar />

      <main className="app-shell">
        <p className="eyebrow">{en ? 'Operations' : 'Exploitation'}</p>
        <h1 className="headline">{en ? 'Drivers' : 'Chauffeurs'}</h1>

        <div className="admin-tabs">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              className={t === tab ? 'is-active' : ''}
              onClick={() => setTab(t)}
            >
              {label[t]}
            </button>
          ))}
        </div>

        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

        {rows === null ? (
          <p className="section-note">{en ? 'Loading' : 'Chargement'}</p>
        ) : rows.length === 0 ? (
          <p className="section-note">
            {en
              ? 'No drivers in this state.'
              : 'Aucun chauffeur dans cet etat.'}
          </p>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>{en ? 'Driver' : 'Chauffeur'}</th>
                <th>{en ? 'Documents' : 'Documents'}</th>
                <th>{en ? 'Status' : 'Statut'}</th>
                <th>{en ? 'Decision' : 'Decision'}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.driver_id}>
                  <td>{d.display_name}</td>
                  <td>
                    {d.missing?.length
                      ? `${d.submitted?.length ?? 0} ${en ? 'on file' : 'au dossier'}, ${d.missing.length} ${en ? 'missing' : 'manquant(s)'}`
                      : `${d.submitted?.length ?? 0} ${en ? 'on file' : 'au dossier'}`}
                  </td>
                  <td>
                    {kycLabel(d.kyc_status, en)},{' '}
                    {d.is_online
                      ? en ? 'online' : 'en ligne'
                      : en ? 'offline' : 'hors ligne'}
                    {d.rejection_reason ? ` (${d.rejection_reason})` : ''}
                  </td>
                  <td>
                    {d.kyc_status === 'verified' ? (
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={busyId === d.driver_id}
                        onClick={() => decide(d, 'suspended')}
                      >
                        {en ? 'Suspend' : 'Suspendre'}
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={busyId === d.driver_id || d.missing?.length > 0}
                          title={
                            d.missing?.length
                              ? en
                                ? 'Refused while a required document is missing'
                                : 'Refuse tant qu un document requis est manquant'
                              : undefined
                          }
                          onClick={() => decide(d, 'verified')}
                        >
                          {en ? 'Approve' : 'Approuver'}
                        </button>
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={busyId === d.driver_id}
                          onClick={() => decide(d, 'rejected')}
                        >
                          {en ? 'Reject' : 'Rejeter'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <p className="section-note">
          {en
            ? 'This endpoint returns no phone numbers and no document contents. Approval is refused by the service while a required document is missing, so this screen cannot grant an exception.'
            : "Cet endpoint ne renvoie ni numero de telephone ni contenu de document. L'approbation est refusee par le service tant qu'un document requis manque, donc cet ecran ne peut accorder aucune exception."}
        </p>
      </main>
    </div>
  );
}
