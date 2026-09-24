// Thin wrapper around the Flask/SQLite API.
//
// Served by Flask on port 8125 → same origin. Opened from GitHub Pages → the API on the
// boss's own machine, so employee data never leaves it.
export const LOCAL_API = "http://127.0.0.1:8125";
export const API_BASE = location.port === "8125" ? "" : LOCAL_API;

export class OfflineError extends Error {}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(API_BASE + path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new OfflineError("Kan ikke få forbindelse til MUSPrepping på din computer");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.detail || `Fejl ${response.status}`, response.status);
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body = {}) => request("POST", path, body),
  put: (path, body) => request("PUT", path, body),
  patch: (path, body) => request("PATCH", path, body),
  del: (path) => request("DELETE", path),
};
