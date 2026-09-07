import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    navigate('/passenger/home'); // stub — real auth wires here later
  };

  return (
    <main className="app-shell">
      <h1>Log in</h1>
      <form onSubmit={handleSubmit} className="form-stack">
        <input placeholder="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input placeholder="Password" type="password" />
        <button className="primary-button" type="submit">Log in</button>
      </form>
      <p>No account? <Link to="/signup">Sign up</Link></p>
    </main>
  );
}