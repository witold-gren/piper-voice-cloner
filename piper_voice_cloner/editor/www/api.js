// The editor's server: JSON in and out. An error carries the server's code and values. Every request
// has a time limit (an answer that never comes must not leave the page waiting for ever).

export const REQUEST_TIMEOUT_MS = 15000;
export const UPLOAD_TIMEOUT_MS = 600000; // a ZIP of 1500 clips over Wi-Fi

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || body?.error || `HTTP ${status}`);
    this.status = status;
    this.code = body?.error;
    this.values = body ?? {};
  }
}

function timeoutMs(form) {
  // tests shorten it (window.pvcRequestTimeoutMs) to see the message without waiting
  return window.pvcRequestTimeoutMs ?? (form ? UPLOAD_TIMEOUT_MS : REQUEST_TIMEOUT_MS);
}

export async function call(path, { method = "GET", body, form } = {}) {
  const controller = new AbortController();
  const limit = timeoutMs(form);
  const timer = setTimeout(() => controller.abort(), limit);
  const options = { method, credentials: "same-origin", headers: {}, signal: controller.signal };
  if (form) options.body = form;
  else if (body !== undefined) {
    options.body = JSON.stringify(body);
    options.headers["Content-Type"] = "application/json";
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    if (err.name === "AbortError") throw new ApiError(0, { error: "timeout", seconds: Math.round(limit / 1000) });
    throw new ApiError(0, { error: "offline", message: err.message });
  } finally {
    clearTimeout(timer);
  }
  if (response.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, { error: "login" });
  }
  const data = response.headers.get("content-type")?.includes("json") ? await response.json() : null;
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export const get = (path) => call(path);
export const post = (path, body) => call(path, { method: "POST", body: body ?? {} });

// a file of the data folder (players, downloads)
export const fileUrl = (relative) => `/api/files/${relative.split("/").map(encodeURIComponent).join("/")}`;
