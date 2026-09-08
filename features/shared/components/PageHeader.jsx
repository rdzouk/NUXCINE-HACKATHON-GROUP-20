import { useNavigate } from 'react-router-dom';
import Icon from './Icon';

/**
 * Back, title, and whatever the screen needs on the right.
 *
 * Every secondary screen needs a way out, and until now several had none: you
 * could reach Notifications and then be stuck there with no control on screen,
 * because a browser back button is not something a phone user sees in an
 * installed PWA. That is a dead end, not a design choice.
 *
 * `navigate(-1)` where there is history, and an explicit `fallback` where
 * there is not, because a deep link opened cold has nothing to go back to and
 * would otherwise leave the passenger exactly as stuck.
 */
export default function PageHeader({ title, eyebrow, fallback = '/', right = null }) {
  const navigate = useNavigate();

  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(fallback, { replace: true });
    }
  };

  return (
    <header className="page-header">
      <button
        type="button"
        className="icon-button"
        onClick={goBack}
        aria-label="Go back"
      >
        <Icon name="back" />
      </button>

      <div className="page-header__titles">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        {title ? <h1>{title}</h1> : null}
      </div>

      {right}
    </header>
  );
}
