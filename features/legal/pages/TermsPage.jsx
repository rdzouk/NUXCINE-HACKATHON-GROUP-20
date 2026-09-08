import PageHeader from '../../shared/components/PageHeader';
export default function TermsPage() {
  return (
    <main className="app-shell legal-page">
      <PageHeader title="Terms" fallback="/passenger/profile" />
      <p className="eyebrow">Last updated: September 2026</p>

      <h3>What VORA is</h3>
      <p>VORA connects passengers who need a ride with independent drivers offering one. VORA does not own or operate vehicles; drivers are independent, and rides are agreements between passenger and driver, facilitated by the platform.</p>

      <h3>Using the app</h3>
      <p>You must provide accurate account information and use a phone number you control. Fare estimates are calculated before you confirm a ride; the final fare may vary slightly if the route changes during the trip.</p>

      <h3>Payment</h3>
      <p>Payment methods available in this version are simulated for demonstration purposes. A production release would integrate real local payment methods (mobile money, cash).</p>

      <h3>Conduct and safety</h3>
      <p>Passengers and drivers are expected to treat each other respectfully. Misuse of the SOS/emergency feature for non-emergencies may result in account suspension. Genuine safety reports are taken seriously and reviewed by our team.</p>

      <h3>Cancellations</h3>
      <p>Either party may cancel a ride before it starts. Repeated cancellations may affect your account standing.</p>

      <h3>Changes</h3>
      <p>These terms may be updated; continued use of the app means you accept the current version.</p>
    </main>
  );
}
