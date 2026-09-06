export default function SupportPage() {
  return (
    <main className="app-shell">
      <h1>Support</h1>
      <p>Need help with a ride? Contact us:</p>
      <ul>
        <li>📞 Call assistance: +237 6XX XXX XXX</li>
        <li>✉️ Email: support@vora.cm</li>
      </ul>
      <textarea placeholder="Describe your issue..." rows={4} />
      <button className="primary-button">Send</button>
    </main>
  );
}