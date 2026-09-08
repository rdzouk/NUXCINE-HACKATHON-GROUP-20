import NotBuilt from '../components/NotBuilt';
import { getLocale } from '../../shared/services/locale';

export default function StatsPage() {
  const en = getLocale() === 'en';

  return (
    <NotBuilt
      title={en ? 'Statistics' : 'Statistiques'}
      endpoint="GET /admin/stats"
      note={
        en
          ? 'The counts the dashboard can honestly show are already on the overview screen, derived from the driver list. Anything beyond that needs an aggregation endpoint rather than a chart drawn over invented numbers.'
          : "Les chiffres que le tableau de bord peut montrer honnetement sont deja sur l'ecran de synthese, derives de la liste des chauffeurs. Au-dela, il faut un endpoint d'agregation, pas un graphique trace sur des nombres inventes."
      }
    />
  );
}
