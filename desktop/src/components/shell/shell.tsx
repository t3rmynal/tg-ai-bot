"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  MessageSquareText,
  Moon,
  Network,
  Server,
  Settings2,
  Sun,
  UserRound,
  Users,
} from "lucide-react";

import { useLive } from "@/lib/live";
import { useRuntime, useSetEnabled, useUpdates } from "@/lib/queries";
import { useTheme } from "@/lib/theme";
import { Switch } from "@/components/ui/switch";

const NAV = [
  { href: "/", label: "dashboard", icon: Activity, n: "01" },
  { href: "/providers/", label: "providers", icon: Server, n: "02" },
  { href: "/persona/", label: "persona", icon: UserRound, n: "03" },
  { href: "/chats/", label: "chats", icon: Users, n: "04" },
  { href: "/proxy/", label: "proxy", icon: Network, n: "05" },
  { href: "/settings/", label: "settings", icon: Settings2, n: "06" },
  { href: "/test/", label: "test chat", icon: MessageSquareText, n: "07" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { connected } = useLive();
  const runtime = useRuntime();
  const setEnabled = useSetEnabled();
  const updates = useUpdates();
  const { resolved, toggle } = useTheme();

  const enabled = runtime.data?.enabled ?? false;

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 flex w-[220px] flex-col border-r border-line-1 bg-bg-1">
        <div
          className="bevel flex h-14 items-center gap-2.5 border-b border-line-1 px-5"
          data-tauri-drag-region
        >
          <span
            aria-hidden
            className={`size-2 rounded-full transition-colors ${enabled ? "bg-accent shadow-[0_0_8px_var(--line-glow)]" : "bg-text-3"}`}
          />
          <span className="display text-base tracking-wide text-text-1">tgai</span>
        </div>
        <nav className="mt-3 flex flex-col gap-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon, n }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`group relative flex h-9 items-center gap-2.5 rounded-sm px-2.5 text-sm
                  transition-colors duration-150 ${
                    active
                      ? "bg-accent-dim text-accent"
                      : "text-text-2 hover:bg-bg-3 hover:text-text-1"
                  }`}
              >
                {active ? (
                  <span
                    aria-hidden
                    className="absolute top-1.5 bottom-1.5 -left-3 w-0.5 bg-accent
                      shadow-[0_0_8px_var(--line-glow)]"
                  />
                ) : null}
                <Icon size={15} strokeWidth={1.5} />
                <span className="flex-1">{label}</span>
                <span className="mono text-[10px] text-text-3">{n}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto px-5 py-4">
          {updates.data?.update_available ? (
            <Link
              href="/settings/"
              className="mono text-xs text-accent transition-colors duration-150 hover:underline"
            >
              v{runtime.data?.version ?? "..."} : v{updates.data.latest} available
            </Link>
          ) : (
            <p className="mono text-xs text-text-3">v{runtime.data?.version ?? "..."}</p>
          )}
        </div>
      </aside>

      <div className="ml-[220px] flex min-h-screen flex-1 flex-col">
        <header
          className="sticky top-0 z-30 flex h-14 items-center justify-between border-b
            border-line-1 bg-bg-0/85 px-6 backdrop-blur"
          data-tauri-drag-region
        >
          <p className="mono text-xs text-text-2">
            {runtime.data ? (
              <>
                {runtime.data.provider_label || runtime.data.provider}
                <span className="text-text-3"> / </span>
                {runtime.data.model || "no model"}
              </>
            ) : (
              "..."
            )}
          </p>
          <div className="flex items-center gap-5">
            <span
              className={`mono flex items-center gap-1.5 text-xs ${
                connected ? "text-text-3" : "text-warn"
              }`}
            >
              <span
                aria-hidden
                className={`size-1.5 rounded-full ${connected ? "bg-text-3" : "bg-warn"}`}
              />
              {connected ? "live" : "reconnecting"}
            </span>
            <button
              onClick={toggle}
              aria-label="toggle theme"
              className="rounded-sm p-1.5 text-text-3 transition-colors duration-150
                hover:bg-bg-3 hover:text-text-1"
            >
              {resolved === "dark" ? (
                <Sun size={15} strokeWidth={1.5} />
              ) : (
                <Moon size={15} strokeWidth={1.5} />
              )}
            </button>
            <div className="flex items-center gap-2">
              <span className="label">{enabled ? "running" : "paused"}</span>
              <Switch checked={enabled} onCheckedChange={(v) => setEnabled.mutate(v)} />
            </div>
          </div>
        </header>
        <main key={pathname} className="animate-fade flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
