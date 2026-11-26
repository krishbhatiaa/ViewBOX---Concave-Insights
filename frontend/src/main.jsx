import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

const clean = (value) => (value || "")
  .replace(/\r/g, "")
  .replace(/\n/g, "")
  .replace(/;/g, "")
  .replace(/\0/g, "")
  .slice(0, 64);

const render = () => ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

const persistAttribution = async () => {
  const qs = new URLSearchParams(window.location.search);
  const params = new URLSearchParams();
  const src = clean(qs.get("src"));
  const ref = clean(qs.get("ref"));
  if (src) params.set("src", src);
  if (ref) params.set("ref", ref);
  if (!params.toString()) return;
  try {
    const res = await fetch(`/api/links/sign?${params}`);
    if (!res.ok) return;
    const signed = await res.json();
    if (signed.src) {
      localStorage.setItem("vb_src", signed.src);
      if (!localStorage.getItem("vb_first")) localStorage.setItem("vb_first", signed.src);
    }
    if (signed.ref) localStorage.setItem("vb_ref", signed.ref);
  } catch {
    return;
  }
};

persistAttribution().finally(render);
