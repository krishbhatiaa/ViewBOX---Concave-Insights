export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export const tokens = {
  get(member) {
    return member ? localStorage.getItem("mt") : localStorage.getItem("at");
  },
  set(member, value) {
    if (value) localStorage.setItem(member ? "mt" : "at", value);
    else localStorage.removeItem(member ? "mt" : "at");
  },
  clearAll() {
    localStorage.removeItem("mt");
    localStorage.removeItem("at");
  },
};

function parseDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e?.msg || "").replace(/^Value error, /, "") || "Invalid value")
      .join(" ");
  }
  return "Please check the details you entered and try again.";
}

export async function api(path, { method = "GET", body, role, raw = false } = {}) {
  const headers = {};
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = role ? tokens.get(role === "member") : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection.", 0);
  }

  if (!res.ok) {
    let detail;
    try {
      const d = await res.json();
      detail = d.detail;
    } catch {
      detail = null;
    }
    if (res.status === 401 && role) tokens.set(role === "member", null);
    throw new ApiError(parseDetail(detail) || "Something went wrong. Please try again.", res.status);
  }

  if (raw) return res.blob();
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.blob();
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
