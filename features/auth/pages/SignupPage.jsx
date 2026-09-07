import { useNavigate } from 'react-router-dom';

export default function SignupPage() {
  const navigate = useNavigate();
  const handleSubmit = (e) => {
    e.preventDefault();
    navigate('/login');
  };

  return (
    <main className="app-shell">
      <h1>Create account</h1>
      <form onSubmit={handleSubmit} className="form-stack">
        <input placeholder="Full name" />
        <input placeholder="Phone number" />
        <input placeholder="Password" type="password" />
        <button className="primary-button" type="submit">Sign up</button>
      </form>
    </main>
  );
}