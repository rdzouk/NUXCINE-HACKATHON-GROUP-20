import NotBuilt from '../components/NotBuilt';
import { getLocale } from '../../shared/services/locale';

export default function UsersPage() {
  const en = getLocale() === 'en';

  return (
    <NotBuilt
      title={en ? 'Users' : 'Utilisateurs'}
      endpoint="GET /admin/users, POST /admin/users/{id}/status"
      note={
        en
          ? 'Suspending an account is a real power and would need an audit row per decision, the same way the KYC decision already writes one. It was not worth shipping half.'
          : "Suspendre un compte est un pouvoir reel et exigerait une ligne d'audit par decision, comme le fait deja la decision KYC. Cela ne valait pas la peine d'en livrer la moitie."
      }
    />
  );
}
