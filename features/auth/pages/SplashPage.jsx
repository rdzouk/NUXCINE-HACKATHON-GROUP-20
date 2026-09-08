import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon, { VoraMark } from '../../shared/components/Icon';
import LanguageToggle from '../../shared/components/LanguageToggle';
import { getLocale } from '../../shared/services/locale';
import { getAccessToken, getRouteForRole, getStoredUser } from '../services/session';

/**
 * The first screen, laid out the way the brand's own reference screen is:
 * wordmark, letterspaced eyebrow, two-tone headline, one supporting line, and
 * a single lime call to action.
 *
 * The three points below the headline are the two bets and the safety
 * mechanism, because this is the last moment before login where a jury reads
 * anything, and "another ride-hailing app" is the wrong first impression.
 *
 * **The language toggle belongs here**, not only behind a login. This was
 * written in English while the app defaults to French, so the first screen
 * anybody sees was in the wrong language and the only way to change it was
 * three screens deep, past an account you might not have.
 *
 * A signed-in user is sent straight through. A splash you have to tap past to
 * reach your own app is friction with no purpose.
 */
export default function SplashPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const en = getLocale() === 'en';

  useEffect(() => {
    const token = getAccessToken();
    const user = getStoredUser();

    if (token && user?.role) {
      navigate(getRouteForRole(user.role), { replace: true });
      return;
    }

    const t = setTimeout(() => setReady(true), 120);
    return () => clearTimeout(t);
  }, [navigate]);

  return (
    <main className={ready ? 'app-shell splash is-ready' : 'app-shell splash'}>
      <div className="splash__glow" aria-hidden="true" />

      <div className="splash__top">
        <div className="wordmark">
          <VoraMark size={30} />
          <span>VORA</span>
        </div>
        <LanguageToggle />
      </div>

      <div className="splash__copy">
        <p className="eyebrow">
          {en ? 'Smart mobility' : 'Mobilite intelligente'}
          <br />
          {en ? 'for Cameroon' : 'pour le Cameroun'}
        </p>
        <h1 className="headline">
          {en ? 'Your city.' : 'Votre ville.'}
          <em>{en ? 'Your ride.' : 'Votre course.'}</em>
        </h1>
        <p className="section-note">
          {en ? 'Safe. Reliable. Affordable.' : 'Sure. Fiable. Abordable.'}
          <br />
          {en ? 'Built for how you move.' : 'Concu pour vos deplacements.'}
        </p>
      </div>

      <ul className="splash__points">
        <li>
          <span className="splash__icon"><Icon name="pin" /></span>
          <span>
            <strong>
              {en
                ? 'Carrefour Warda, not 12 Rue X'
                : 'Carrefour Warda, pas 12 Rue X'}
            </strong>
            <span>
              {en
                ? '5454 real landmarks. Spelling optional.'
                : '5454 reperes reels. Orthographe facultative.'}
            </span>
          </span>
        </li>
        <li>
          <span className="splash__icon"><Icon name="route" /></span>
          <span>
            <strong>
              {en
                ? 'Share a corridor, pay for your seat'
                : 'Partagez un corridor, payez votre place'}
            </strong>
            <span>
              {en
                ? 'You pay less. The driver earns more.'
                : 'Vous payez moins. Le chauffeur gagne plus.'}
            </span>
          </span>
        </li>
        <li>
          <span className="splash__icon"><Icon name="shield" /></span>
          <span>
            <strong>
              {en ? 'A PIN at every pickup' : 'Un code a chaque prise en charge'}
            </strong>
            <span>
              {en
                ? 'The one thing a stranger cannot know.'
                : "La seule chose qu'un inconnu ne peut pas savoir."}
            </span>
          </span>
        </li>
      </ul>

      <button className="primary-button" onClick={() => navigate('/login')}>
        {en ? 'Get started' : 'Commencer'}
        <Icon name="arrow" size={18} />
      </button>
    </main>
  );
}
