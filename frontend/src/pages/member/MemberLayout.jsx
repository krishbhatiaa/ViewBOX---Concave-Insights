import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { tokens } from "../../api.js";
import ThemeToggle from "../../components/ThemeToggle.jsx";
import { Button } from "../../components/ui.jsx";

const linkCls = ({ isActive }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition min-h-11 inline-flex items-center ${
    isActive
      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;

export default function MemberLayout() {
  const navigate = useNavigate();
  const token = tokens.get(true);
  useEffect(() => {
    if (!token) navigate("/login", { replace: true });
  }, [token, navigate]);
  if (!token) return null;
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-2">
          <span className="text-base font-bold tracking-tight text-indigo-600 dark:text-indigo-400">ViewBox</span>
          <nav aria-label="Member" className="flex items-center gap-1">
            <NavLink to="/home" className={linkCls}>
              Home
            </NavLink>
            <NavLink to="/referrals" className={linkCls}>
              My referrals
            </NavLink>
          </nav>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button
              variant="ghost"
              className="min-h-11 !px-2 !text-xs"
              onClick={() => {
                tokens.set(true, null);
                navigate("/login", { replace: true });
              }}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-5">
        <Outlet />
      </main>
    </div>
  );
}
