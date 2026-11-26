import { useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import ThemeToggle from "../../components/ThemeToggle.jsx";
import { useToast } from "../../components/Toast.jsx";
import { Button } from "../../components/ui.jsx";

const linkCls = ({ isActive }) =>
  `inline-flex min-h-11 items-center rounded-[2px] border px-3 py-2 font-mono text-xs uppercase tracking-wide transition-colors ${
    isActive
      ? "border-deep bg-deep/10 text-deep"
      : "border-transparent text-ink-3 hover:bg-paper-2 hover:text-ink"
  }`;

const tabCls = ({ isActive }) =>
  `flex min-h-11 flex-1 flex-col items-center justify-center gap-1 border-t-2 font-mono text-[10px] uppercase tracking-wide ${
    isActive ? "border-t-acc bg-paper-3 text-ink" : "border-t-transparent text-ink-3"
  }`;

export default function MemberLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const token = tokens.get(true);
  useEffect(() => {
    if (!token) navigate("/login", { replace: true });
  }, [token, navigate]);
  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    api("/api/me", { role: "member" })
      .then((me) => {
        if (active && !me.profile_complete && location.pathname !== "/profile") {
          navigate("/profile", { replace: true });
        }
      })
      .catch((err) => {
        if (active) toast(err.message, "error");
      });
    return () => {
      active = false;
    };
  }, [token, location.pathname, navigate, toast]);
  if (!token) return null;
  return (
    <div className="min-h-dvh bg-paper text-ink">
      <header className="sticky top-0 z-30 min-h-14 border-b border-line-2 bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-2">
          <span className="font-display text-xl font-normal tracking-tight">ViewBox</span>
          <nav aria-label="Member" className="hidden items-center gap-1 sm:flex">
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
      <main className="viewbox-enter mx-auto max-w-5xl px-4 pb-24 pt-6 sm:pb-10">
        <Outlet />
      </main>
      <nav aria-label="Member mobile" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line-2 bg-paper sm:hidden">
        <NavLink to="/home" className={tabCls}>
          <span aria-hidden="true" className="h-2 w-2 bg-current" />
          Home
        </NavLink>
        <NavLink to="/referrals" className={tabCls}>
          <span aria-hidden="true" className="h-2 w-2 bg-current" />
          Referrals
        </NavLink>
      </nav>
    </div>
  );
}
