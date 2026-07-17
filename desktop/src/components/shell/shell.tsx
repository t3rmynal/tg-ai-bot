"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  MessageSquareText,
  Server,
  Settings2,
  UserRound,
  Users,
} from "lucide-react";

import { useLive } from "@/lib/live";
import { useRuntime, useSetEnabled, useUpdates } from "@/lib/queries";
import { Switch } from "@/components/ui/switch";

const NAV = [
  { href: "/", label: "dashboard", icon: Activity },
  { href: "/providers/", label: "providers", icon: Server },
  { href: "/persona/", label: "persona", icon: UserRound },
  { href: "/chats/", label: "chats", icon: Users },
  { href: "/settings/", label: "settings", icon: Settings2 },
  { href: "/test/", label: "test chat", icon: MessageSquareText },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { connected } = useLive();
  const runtime = useRuntime();
  const setEnabled = useSetEnabled();
  const updates = useUpdates();

  const enabled = runtime.data?.enabled ?? false;

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 flex w-[208px] flex-col border-r border-line-1 bg-bg-1">
        <div className="flex h-12 items-center gap-2 px-5" data-tauri-drag-region>
          <span
            aria-hidden
            className={`size-2 rounded-full ${enabled ? "bg-ok" : "bg-text-3"}`}
          />
          <span className="mono text-sm font-medium tracking-wide text-text-1">tgai</span>
        </div>
        <nav className="mt-2 flex flex-col gap-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm
                  transition-colors duration-120 ${
                    active
                      ? "bg-accent-dim text-accent"
                      : "text-text-2 hover:bg-bg-3 hover:text-text-1"
                  }`}
              >
                {active ? (
                  <span
                    aria-hidden
                    className="absolute top-1.5 bottom-1.5 -left-3 w-px bg-accent shadow-[0_0_6px_var(--color-line-glow)]"
                  />
                ) : null}
                <Icon size={15} strokeWidth={1.5} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto px-5 py-4">
          {updates.data?.update_available ? (
            <Link
              href="/settings/"
              className="mono text-xs text-accent transition-colors duration-120 hover:underline"
            >
              v{runtime.data?.version ?? "..."} : v{updates.data.latest} available
            </Link>
          ) : (
            <p className="mono text-xs text-text-3">v{runtime.data?.version ?? "..."}</p>
          )}
        </div>
      </aside>

      <div className="ml-[208px] flex min-h-screen flex-1 flex-col">
        <header
          className="sticky top-0 z-30 flex h-12 items-center justify-between border-b
            border-line-1 bg-bg-0/90 px-6 backdrop-blur"
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
          <div className="flex items-center gap-4">
            <span
              className={`flex items-center gap-1.5 text-xs ${
                connected ? "text-text-3" : "text-warn"
              }`}
            >
              <span
                aria-hidden
                className={`size-1.5 rounded-full ${connected ? "bg-text-3" : "bg-warn"}`}
              />
              {connected ? "live" : "reconnecting"}
            </span>
            <div className="flex items-center gap-2">
              <span className="label">{enabled ? "on" : "off"}</span>
              <Switch
                checked={enabled}
                onCheckedChange={(v) => setEnabled.mutate(v)}
                success
              />
            </div>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
