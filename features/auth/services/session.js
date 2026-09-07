const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const SESSION_USER_KEY = 'session_user';

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUser() {
  const rawUser = localStorage.getItem(SESSION_USER_KEY);

  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser);
  } catch {
    localStorage.removeItem(SESSION_USER_KEY);
    return null;
  }
}

export function storeSession(session) {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);

  if (session.user) {
    localStorage.setItem(SESSION_USER_KEY, JSON.stringify(session.user));
  }
}

export function storeRefreshedSession(session) {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(SESSION_USER_KEY);
}

export function getRouteForRole(role) {
  switch (role) {
    case 'driver':
      return '/driver/dashboard';
    case 'admin':
      return '/admin/dashboard';
    case 'passenger':
    default:
      return '/passenger/home';
  }
}

