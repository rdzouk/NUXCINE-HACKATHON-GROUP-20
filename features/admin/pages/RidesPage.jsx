import NotBuilt from '../components/NotBuilt';
import { getLocale } from '../../shared/services/locale';

export default function RidesPage() {
  const en = getLocale() === 'en';

  return (
    <NotBuilt
      title={en ? 'Rides' : 'Courses'}
      endpoint="GET /admin/rides"
      note={
        en
          ? 'A ride carries both parties and a fare, so an operator-wide listing is a privacy decision before it is a feature. It would need a documented retention window and a reason recorded per lookup.'
          : "Une course porte les deux parties et un tarif, donc une liste a l'echelle de la plateforme est une decision de confidentialite avant d'etre une fonctionnalite. Il faudrait une duree de conservation documentee et un motif enregistre a chaque consultation."
      }
    />
  );
}
