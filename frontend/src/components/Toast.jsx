import { createContext, useCallback, useContext, useEffect, useState } from "react";

const ToastContext = createContext(() => {});
const SESSION_EXPIRED_KEY = "vb_session_expired";

let nextId = 0;
let sessionExpiredHandler = null;

export function notifySessionExpired() {
  sessionExpiredHandler?.();
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (message, type = "success") => {
      const id = ++nextId;
      setToasts((t) => [...t, { id, message, type }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss]
  );

  useEffect(() => {
    const handler = () => toast("Session expired, please log in again", "error");
    sessionExpiredHandler = handler;
    if (sessionStorage.getItem(SESSION_EXPIRED_KEY)) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
      handler();
    }
    return () => {
      if (sessionExpiredHandler === handler) sessionExpiredHandler = null;
    };
  }, [toast]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto flex max-w-md items-start gap-3 rounded-[2px] border border-l-4 bg-paper px-4 py-3 font-mono text-xs text-ink ${
              t.type === "error" ? "border-acc" : "border-deep"
            }`}
          >
            <span className="flex-1">
              <span className="mr-2 font-semibold uppercase tracking-wide text-ink-3">
                {t.type === "error" ? "Alert" : "OK"}
              </span>
              {t.message}
            </span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              className="-m-1 flex h-11 w-11 items-center justify-center rounded-[2px] text-ink-3 hover:text-ink"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
