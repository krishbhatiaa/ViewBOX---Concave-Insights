import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

const qs = new URLSearchParams(window.location.search);
if (qs.get("src")) {
  localStorage.setItem("vb_src", qs.get("src"));
  if (!localStorage.getItem("vb_first")) localStorage.setItem("vb_first", qs.get("src"));
}
if (qs.get("ref")) localStorage.setItem("vb_ref", qs.get("ref"));

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
