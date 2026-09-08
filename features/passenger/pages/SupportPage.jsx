import { Link } from 'react-router-dom';
import PageHeader from '../../shared/components/PageHeader';

export default function SupportPage() {
  return (
    <main className="app-shell">
      <PageHeader title="Support" fallback="/passenger/home" />
      <p>Need help with a ride? Contact us:</p>
      <ul>
        <li>📞 Call assistance: +237 6XX XXX XXX</li>
        <li>✉️ Email: support@vora.cm</li>
      </ul>
      <textarea placeholder="Describe your issue..." rows={4} />
      <button className="primary-button">Send</button>
      <div className="legal-links">
        <Link to="/legal/privacy">Privacy Policy</Link>
        <Link to="/legal/terms">Terms &amp; Conditions</Link>
      </div>
    </main>
  );
}