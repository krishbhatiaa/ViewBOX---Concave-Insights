import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { tokens } from "./api.js";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import { ToastProvider } from "./components/Toast.jsx";
import { applyTheme } from "./components/ThemeToggle.jsx";
import { Button, Card, PageHeader } from "./components/ui.jsx";
import AdminLayout from "./pages/admin/AdminLayout.jsx";
import AdminLoginPage from "./pages/admin/AdminLoginPage.jsx";
import AdminReferralsPage from "./pages/admin/AdminReferralsPage.jsx";
import FraudPage from "./pages/admin/FraudPage.jsx";
import GridPage from "./pages/admin/GridPage.jsx";
import ImportPage from "./pages/admin/ImportPage.jsx";
import MetaLeadsPage from "./pages/admin/MetaLeadsPage.jsx";
import MetaSimulator from "./pages/MetaSimulator.jsx";
import PayoutsPage from "./pages/admin/PayoutsPage.jsx";
import SourcesPage from "./pages/admin/SourcesPage.jsx";
import StatsPage from "./pages/admin/StatsPage.jsx";
import SurveysPage from "./pages/admin/SurveysPage.jsx";
import HomePage from "./pages/member/HomePage.jsx";
import MemberLayout from "./pages/member/MemberLayout.jsx";
import PhonePage from "./pages/member/PhonePage.jsx";
import ProfilePage from "./pages/member/ProfilePage.jsx";
import ReferralsPage from "./pages/member/ReferralsPage.jsx";

function HomeOrLogin() {
  const location = useLocation();
  if (tokens.get(true)) return <Navigate to="/home" replace />;
  // /signup?src=.. keeps the link params while routing to the phone step
  if (location.pathname === "/signup") return <Navigate to={`/login${location.search}`} replace />;
  return <Navigate to="/login" replace />;
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <Card className="text-center">
        <PageHeader title="Page not found" description="That page does not exist." />
        <div className="flex justify-center gap-2">
          <Button onClick={() => window.location.assign("/")}>Go home</Button>
          <Button variant="secondary" onClick={() => window.location.assign("/admin")}>
            Admin
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default function App() {
  useEffect(() => {
    const saved = localStorage.getItem("vb_theme");
    applyTheme(["system", "light", "dark"].includes(saved) ? saved : "system");
  }, []);
  return (
    <ErrorBoundary>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<HomeOrLogin />} />
          <Route path="/signup" element={<HomeOrLogin />} />
          <Route path="/login" element={<PhonePage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route element={<MemberLayout />}>
            <Route path="/home" element={<HomePage />} />
            <Route path="/referrals" element={<ReferralsPage />} />
          </Route>

          <Route path="/admin" element={<AdminLoginPage />} />
          <Route element={<AdminLayout />}>
            <Route path="/admin/members" element={<GridPage />} />
            <Route path="/admin/referrals" element={<AdminReferralsPage />} />
            <Route path="/admin/surveys" element={<SurveysPage />} />
            <Route path="/admin/sources" element={<SourcesPage />} />
            <Route path="/admin/stats" element={<StatsPage />} />
            <Route path="/admin/import" element={<ImportPage />} />
            <Route path="/admin/meta-leads" element={<MetaLeadsPage />} />
            <Route path="/admin/meta-simulator" element={<MetaSimulator />} />
            <Route path="/admin/payouts" element={<PayoutsPage />} />
            <Route path="/admin/fraud" element={<FraudPage />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </ToastProvider>
    </ErrorBoundary>
  );
}
