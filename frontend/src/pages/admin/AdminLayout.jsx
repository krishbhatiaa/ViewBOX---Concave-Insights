import { useEffect, useRef } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { tokens } from "../../api.js";
import { Button } from "../../components/ui.jsx";

const tabs = [
  { to: "/admin/members", label: "Members" },
  { to: "/admin/surveys", label: "Surveys" },
  { to: "/admin/sources", label: "Sources" },
  { to: "/admin/stats", label: "Source stats" },
  { to: "/admin/import", label: "Import CSV" },
  { to: "/admin/meta-leads", label: "Meta leads" },
  { to: "/admin/payouts", label: "Payouts" },
  { to: "/admin/fraud", label: "Fraud queue" },
];

const linkCls = ({ isActive }) =>
  `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-11 inline-flex items-center ${
    isActive
      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;

export default function AdminLayout() {
  const navigate = useNavigate();
  const headerRef = useRef(null);
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
    <div className="min-h-dvh">
      <header ref={headerRef} className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2">
          <span className="text-base font-bold tracking-tight">
            ViewBox <span className="text-indigo-600 dark:text-indigo-400">Admin</span>
          </span>
          <nav aria-label="Admin" className="order-3 flex w-full items-center gap-1 overflow-x-auto sm:order-2 sm:w-auto sm:flex-1 sm:justify-center">
            {tabs.map((t) => (
              <NavLink key={t.to} to={t.to} className={linkCls}>
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="order-2 sm:order-3">
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
      <main className="mx-auto max-w-6xl px-4 py-5">
        <Outlet />
      </main>
    </div>
  );
}
