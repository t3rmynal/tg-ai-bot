"use client";

// theme follows the system, a toggle can pin light or dark to localStorage

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

type Mode = "system" | "light" | "dark";
type Resolved = "light" | "dark";

interface ThemeState {
  mode: Mode;
  resolved: Resolved;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState>({
  mode: "system",
  resolved: "dark",
  toggle: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function systemPref(): Resolved {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// subscribe to the os theme without a synchronous setState in an effect
function subscribeSystem(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // the inline layout script already applied the saved theme to data-theme,
  // so read it back here to avoid a setState in an effect
  const [mode, setMode] = useState<Mode>(() => {
    if (typeof document === "undefined") return "system";
    const attr = document.documentElement.getAttribute("data-theme");
    return attr === "dark" || attr === "light" ? attr : "system";
  });
  const system = useSyncExternalStore(subscribeSystem, systemPref, () => "dark" as Resolved);

  const resolved: Resolved = mode === "system" ? system : mode;

  useEffect(() => {
    const root = document.documentElement;
    if (mode === "system") {
      root.removeAttribute("data-theme");
      localStorage.removeItem("tgai-theme");
    } else {
      root.setAttribute("data-theme", mode);
      localStorage.setItem("tgai-theme", mode);
    }
  }, [mode]);

  const toggle = useCallback(() => {
    setMode((prev) => {
      const current = prev === "system" ? systemPref() : prev;
      return current === "dark" ? "light" : "dark";
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ mode, resolved, toggle }}>{children}</ThemeContext.Provider>
  );
}
