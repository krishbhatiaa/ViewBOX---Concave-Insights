import { useEffect, useState } from "react";

const CHOICES = ["system", "light", "dark"];
const LABELS = { system: "Theme: system", light: "Theme: light", dark: "Theme: dark" };

function prefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)");
}

export function applyTheme(choice) {
  const dark = choice === "dark" || (choice === "system" && prefersDark().matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export default function ThemeToggle() {
  const [choice, setChoice] = useState(() => {
    const saved = localStorage.getItem("vb_theme");
    return CHOICES.includes(saved) ? saved : "system";
  });

  useEffect(() => {
    localStorage.setItem("vb_theme", choice);
    applyTheme(choice);
    const media = prefersDark();
    const onChange = () => {
      if (choice === "system") applyTheme("system");
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  const next = CHOICES[(CHOICES.indexOf(choice) + 1) % CHOICES.length];
  return (
    <button
      type="button"
      onClick={() => setChoice(next)}
      aria-label={`${LABELS[choice]}. Switch to ${next}.`}
      title={`${LABELS[choice]} — click for ${next}`}
      className="min-h-11 rounded-lg px-2 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      {LABELS[choice]}
    </button>
  );
}
