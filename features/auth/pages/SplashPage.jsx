import { useNavigate } from 'react-router-dom';

export default function SplashPage() {
  const navigate = useNavigate();
  return (
    <main className="app-shell splash">
      <h1>VORA</h1>
      <p className="eyebrow">Smart mobility for Cameroon</p>
      <button className="primary-button" onClick={() => navigate('/login')}>
        Get started
      </button>
    </main>
  );
}