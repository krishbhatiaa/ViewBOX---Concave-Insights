import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { tokens } from "../../api.js";
import ThemeToggle from "../../components/ThemeToggle.jsx";
import { Button } from "../../components/ui.jsx";

const tabs = [
  { to: "/admin/members", label: "Members" },
  { to: "/admin/referrals", label: "Referrals" },
  { to: "/admin/surveys", label: "Surveys" },
  { to: "/admin/sources", label: "Sources" },
  { to: "/admin/stats", label: "Source stats" },
  { to: "/admin/import", label: "Import CSV" },
  { to: "/admin/meta-leads", label: "Meta leads" },
  { to: "/admin/meta-simulator", label: "Meta simulator" },
  { to: "/admin/payouts", label: "Payouts" },
  { to: "/admin/fraud", label: "Fraud queue" },
];

const linkCls = ({ isActive }) =>
  `inline-flex min-h-11 items-center gap-3 rounded-[2px] border-l-2 px-3 py-2 font-mono text-xs uppercase tracking-wide transition-colors ${
    isActive ? "border-l-acc bg-paper-3 text-ink" : "border-l-transparent text-ink-3 hover:bg-paper-2 hover:text-ink"
  }`;

function AdminNav({ onNavigate }) {
  return (
    <>
      {tabs.map((t, i) => (
        <NavLink key={t.to} to={t.to} className={linkCls} onClick={onNavigate}>
          <span className="text-[10px] text-ink-3">{String(i + 1).padStart(2, "0")}</span>
          {t.label}
        </NavLink>
      ))}
    </>
  );
}

export default function AdminLayout() {
  const navigate = useNavigate();
  const headerRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const token = tokens.get(false);
  useEffect(() => {
    if (!token) navigate("/admin", { replace: true });
  }, [token, navigate]);
  useEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const sync = () => document.documentElement.style.setProperty("--admin-header-h", `${el.offsetHeight}px`);
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  if (!token) return null;
  return (
    <div className="min-h-dvh bg-paper text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-line-2 bg-paper-2 lg:flex">
        <div className="border-b border-line px-4 py-4">
          <p className="font-display text-xl font-normal">ViewBox</p>
          <p className="font-mono text-[10px] uppercase tracking-wide text-acc">Admin</p>
        </div>
        <p className="px-4 pb-2 pt-4 font-mono text-[10px] uppercase tracking-wide text-ink-3">Operations</p>
        <nav aria-label="Admin" className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 pb-4">
          <AdminNav />
        </nav>
      </aside>
      <header ref={headerRef} className="sticky top-0 z-20 min-h-14 border-b border-line-2 bg-paper/95 backdrop-blur lg:ml-56">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Open admin menu"
              aria-expanded={menuOpen}
              aria-controls="admin-menu"
              onClick={() => setMenuOpen(true)}
              className="flex h-11 w-11 items-center justify-center rounded-[2px] border border-line-2 text-ink-2 lg:hidden"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            <span className="font-display text-xl font-normal">ViewBox</span>
            <span className="hidden font-mono text-[10px] uppercase tracking-wide text-acc sm:inline">Admin</span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button
              variant="ghost"
              className="min-h-11 !px-2 !text-xs"
              onClick={() => {
                tokens.set(false, null);
                navigate("/admin", { replace: true });
              }}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      {menuOpen && (
        <div id="admin-menu" className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close admin menu"
            onClick={() => setMenuOpen(false)}
            className="absolute inset-0 bg-ink/60"
          />
          <nav aria-label="Admin mobile" className="absolute inset-y-0 left-0 flex w-72 flex-col overflow-y-auto border-r border-line-2 bg-paper p-4">
            <div className="mb-4 flex items-center justify-between border-b border-line pb-4">
              <span className="font-display text-xl font-normal">ViewBox</span>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close admin menu"
                className="flex h-11 w-11 items-center justify-center rounded-[2px] border border-line-2 text-ink-2"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex flex-col gap-1">
              <AdminNav onNavigate={() => setMenuOpen(false)} />
            </div>
          </nav>
        </div>
      )}
      <main className="lg:pl-56">
        <div className="viewbox-enter mx-auto max-w-6xl px-4 pb-10 pt-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
