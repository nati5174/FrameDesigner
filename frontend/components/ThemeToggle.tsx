"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

export function ThemeToggle() {
  // Start with "system" so first render matches server output (no localStorage on server).
  // Load the real saved value in an effect after mount.
  const [theme, setTheme] = useState<Theme>("system");

  // Load saved theme after mount to avoid hydration mismatch (server has no
  // localStorage). setState is intentional here — one-time post-mount sync.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved === "light" || saved === "dark") {
      setTheme(saved);
      applyTheme(saved);
    }
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  function toggle() {
    // Cycle: system → light → dark → system
    // In practice: infer current effective theme and flip
    const isDarkNow =
      theme === "dark" ||
      (theme === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    const next: Theme = isDarkNow ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    localStorage.setItem("theme", next);
  }

  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
      className="
        flex h-8 w-8 items-center justify-center rounded-md
        text-muted hover:text-text hover:bg-border/40
        transition-colors text-base
      "
    >
      {isDark ? "☀" : "☾"}
    </button>
  );
}
