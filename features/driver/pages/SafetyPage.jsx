import PageHeader from '../../shared/components/PageHeader';
export default function SafetyPage() {
  return (
    <main className="app-shell centered">
      <PageHeader title="Safety" fallback="/driver/dashboard" />
      <button className="sos-button">🆘 Trigger emergency alert</button>
      <button className="secondary-button">Report a passenger</button>
      <button className="secondary-button">Contact assistance</button>
      <button className="secondary-button">Share this ride</button>
    </main>
  );
}