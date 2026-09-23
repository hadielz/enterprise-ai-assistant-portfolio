const API_BASE_URL =
  window.__APP_CONFIG__?.apiBaseUrl ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000/api";

export function getStoredToken() {
  return sessionStorage.getItem("enterprise-ai-token");
}

export function storeToken(token) {
  sessionStorage.setItem("enterprise-ai-token", token);
}

export function clearToken() {
  sessionStorage.removeItem("enterprise-ai-token");
}

export async function loginUser(username, password) {
  // OAuth2PasswordRequestForm expects form-encoded data, not JSON.
  const formData = new URLSearchParams();
  formData.set("username", username);
  formData.set("password", password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Incorrect username or password.");
  }

  return response.json();
}

export async function registerUser({
  username,
  displayName,
  password,
}) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username,
      display_name: displayName,
      password,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);

    throw new Error(
      body?.detail || `Registration failed: HTTP ${response.status}`
    );
  }

  return response.json();
}

export async function getCurrentUser(token) {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/auth/me`,
    { token }
  );

  return response.json();
}

export async function authenticatedFetch(
  url,
  { token = getStoredToken(), headers = {}, ...options } = {}
) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 401) {
    clearToken();
    throw new Error("Your session expired. Please log in again.");
  }

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      errorText || `Backend returned HTTP ${response.status}`
    );
  }

  return response;
}

export { API_BASE_URL };
export async function listTickets() {
  const response = await authenticatedFetch(`${API_BASE_URL}/tickets`);
  return response.json();
}

export async function updateTicketStatus(ticketId, status) {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/status`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    }
  );

  return response.json();
}
