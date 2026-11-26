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
  const segmentCls = (name) =>
    `flex min-h-11 flex-1 items-center justify-center border-r border-line px-1 font-mono text-[9px] uppercase tracking-wide last:border-r-0 sm:px-2 sm:text-[10px] ${
      choice === name ? "bg-paper-3 text-ink" : "text-ink-3"
    }`;
  return (
    <button
      type="button"
      onClick={() => setChoice(next)}
      aria-label={`${LABELS[choice]}. Switch to ${next}.`}
      title={`${LABELS[choice]} — click for ${next}`}
      className="inline-flex min-h-11 items-center rounded-[2px] border border-line bg-paper"
    >
      <span className="hidden px-2 font-mono text-[10px] uppercase tracking-wide text-ink-3 sm:inline">Theme</span>
      <span className="flex" aria-hidden="true">
        {CHOICES.map((name) => (
          <span key={name} className={segmentCls(name)}>
            {name}
          </span>
        ))}
      </span>
    </button>
  );
}
