import { getLocale } from '../../shared/services/locale';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  storeRefreshedSession,
} from '../../auth/services/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const AUTH_PATHS = new Set(['/auth/otp/request', '/auth/otp/verify', '/auth/refresh']);

let refreshPromise = null;

function redirectToLogin() {
  if (typeof window === 'undefined') {
    return;
  }

  if (window.location.pathname !== '/login') {
    window.location.assign('/login');
  }
}

function buildHeaders(token, headers = {}) {
  const mergedHeaders = new Headers(headers);

  if (!mergedHeaders.has('Content-Type')) {
    mergedHeaders.set('Content-Type', 'application/json');
  }

  // The app's language, not the browser's. Without this the API negotiates
  // from Accept-Language and answers an English screen in French, which is
  // how "Send code" came to be followed by "Trop de tentatives."
  if (!mergedHeaders.has('Accept-Language')) {
    mergedHeaders.set('Accept-Language', getLocale());
  }

  if (token) {
    mergedHeaders.set('Authorization', `Bearer ${token}`);
  }

  return mergedHeaders;
}

async function parseResponseBody(res) {
  if (res.status === 204) {
    return null;
  }

  const contentType = res.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return res.json().catch(() => null);
  }

  const text = await res.text().catch(() => '');
  return text || null;
}

function createApiError(res, body) {
  const err = new Error(body?.error?.message ?? 'Request failed');
  err.code = body?.error?.code ?? null;
  err.status = res.status;
  err.details = body?.error?.details ?? null;
  err.requestId = body?.error?.request_id ?? null;
  return err;
}

async function performRequest(path, options = {}, token = getAccessToken()) {
  const { headers, ...restOptions } = options;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...restOptions,
    headers: buildHeaders(token, headers),
  });
  const body = await parseResponseBody(res);
  return { res, body };
}

async function refreshAccessToken() {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    return false;
  }

  refreshPromise = (async () => {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: buildHeaders(null),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const body = await parseResponseBody(res);

    if (!res.ok) {
      throw createApiError(res, body);
    }

    storeRefreshedSession(body);
    return true;
  })();

  try {
    return await refreshPromise;
  } catch {
    clearSession();
    redirectToLogin();
    return false;
  } finally {
    refreshPromise = null;
  }
}

export async function apiFetch(path, options = {}) {
  const { skipAuthRefresh = false, ...requestOptions } = options;
  const { res, body } = await performRequest(path, requestOptions);

  if (res.ok) {
    return body;
  }

  if (res.status === 401 && !skipAuthRefresh && !AUTH_PATHS.has(path)) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      const retried = await performRequest(path, requestOptions, getAccessToken());

      if (retried.res.ok) {
        return retried.body;
      }

      const retryError = createApiError(retried.res, retried.body);

      if (retried.res.status === 401) {
        clearSession();
        redirectToLogin();
      }

      throw retryError;
    }
  }

  const err = createApiError(res, body);

  if (res.status === 401 && path === '/auth/refresh') {
    clearSession();
    redirectToLogin();
  }

  throw err;
}