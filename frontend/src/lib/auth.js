const KEY = "vb_pending";

export function getPending() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export function setPending(value) {
  sessionStorage.setItem(KEY, JSON.stringify(value));
}

export function clearPending() {
  sessionStorage.removeItem(KEY);
}

export function getLinkParams() {
  return {
    src: new URLSearchParams(window.location.search).get("src") || localStorage.getItem("vb_src") || "",
    ref: new URLSearchParams(window.location.search).get("ref") || localStorage.getItem("vb_ref") || "",
    first: localStorage.getItem("vb_first") || "",
  };
}

export function clearLinkParams() {
  ["vb_src", "vb_ref", "vb_first"].forEach((k) => localStorage.removeItem(k));
}
