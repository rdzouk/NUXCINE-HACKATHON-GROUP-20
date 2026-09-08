/**
 * Where the live sockets live.
 *
 * `fetch` accepts a relative path, so the API base can simply be `/api/v1` and
 * the browser resolves it against the page. `new WebSocket()` cannot: it
 * requires an absolute `ws://` or `wss://` URL and throws on anything else.
 *
 * So the socket URL is derived from the page's own location. That is not a
 * convenience, it is the only way to be correct in both places the app runs:
 * over plain http locally and over https through the tunnel. A hardcoded
 * `ws://` fails on an https page because browsers refuse a plaintext socket
 * from a secure origin, and a hardcoded `wss://` fails locally where there is
 * no certificate. Deriving it means one bundle works in both.
 *
 * VITE_WS_BASE_URL still wins when set, for the case where the sockets are
 * genuinely somewhere else.
 */
export function wsBaseUrl() {
  const configured = import.meta.env.VITE_WS_BASE_URL;

  if (configured) {
    return configured.replace(/\/$/, '');
  }

  if (typeof window === 'undefined') {
    return '';
  }

  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

  return `${scheme}//${window.location.host}/api/v1`;
}
