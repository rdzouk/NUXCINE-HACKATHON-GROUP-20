const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('access_token'); // set by whatever auth flow lands first

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const body = await res.json().catch(() => null);

  if (!res.ok) {
    // Matches the contract's error envelope: { error: { code, message, details, request_id } }
    const err = new Error(body?.error?.message ?? 'Request failed');
    err.code = body?.error?.code;
    err.status = res.status;
    throw err;
  }

  return body;
}