import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'mapbox-gl/dist/mapbox-gl.css';
import './styles.css';
import App from './App';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
// Register the service worker so the app installs and opens offline.
//
// After load, never before: registration competes with the first render for
// the same connection, and on a slow network that trade is the wrong way
// round. Failure is ignored on purpose, because a missing worker costs
// installability, not function.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
