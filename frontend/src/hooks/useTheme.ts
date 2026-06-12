/** Dark/light theme toggle persisted to localStorage. */

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

/**
 * Manage the app theme by toggling the `dark`/`light` class on <html>.
 *
 * @returns The current theme and a toggle function.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem("rf-theme") as Theme) ?? "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("dark", "light");
    root.classList.add(theme);
    localStorage.setItem("rf-theme", theme);
  }, [theme]);

  return {
    theme,
    toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
  };
}
