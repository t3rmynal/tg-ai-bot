"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { ArrowDownLeft, ArrowUpRight, CircleAlert, Info, Timer } from "lucide-react";

import { useLive } from "@/lib/live";
import { useChats, useRuntime } from "@/lib/queries";
import { timeOf, uptime } from "@/lib/format";
import { Card, EmptyState, PageHeader } from "@/components/ui/card";
import type { ActivityEvent } from "@/lib/types";

const KIND_STYLE: Record<ActivityEvent["kind"], { icon: typeof Info; className: string }> = {
  incoming: { icon: ArrowDownLeft, className: "text-text-2" },
  reply: { icon: ArrowUpRight, className: "text-accent" },
  wait: { icon: Timer, className: "text-warn" },
  error: { icon: CircleAlert, className: "text-danger" },
  info: { icon: Info, className: "text-text-3" },
};

export default function DashboardPage() {
  const runtime = useRuntime();
  const chats = useChats();
  const { events } = useLive();

  const stats = runtime.data?.stats;
  const tiles = [
    { label: "messages", value: stats?.messages_processed },
    { label: "ai calls", value: stats?.ai_calls },
    { label: "ai errors", value: stats?.ai_errors },
    { label: "rate limits", value: stats?.rate_limited },
    { label: "chats", value: stats?.chats_with_history },
  ];

  return (
    <div className="mx-auto flex max-w-4xl flex-col">
      <PageHeader eyebrow="overview" title="dashboard" index="01" />

      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {tiles.map((t) => (
            <div key={t.label} className="bevel rounded-md border border-line-1 bg-bg-1 px-4 py-3.5">
              <p className="label">{t.label}</p>
              <p className="display mt-1.5 text-2xl leading-none text-text-1">{t.value ?? "..."}</p>
            </div>
          ))}
        </div>

        <Card title="at a glance">
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm sm:grid-cols-3">
            <GlanceItem
              label="provider"
              href="/providers/"
              value={runtime.data?.provider_label || runtime.data?.provider || "..."}
            />
            <GlanceItem label="model" href="/providers/" value={runtime.data?.model || "not set"} mono />
            <GlanceItem label="persona" href="/persona/" value={runtime.data?.persona || "..."} />
            <GlanceItem
              label="rate cap"
              href="/providers/"
              value={runtime.data ? `${runtime.data.rpm} rpm` : "..."}
              mono
            />
            <GlanceItem
              label="whitelist / blacklist"
              href="/chats/"
              value={
                chats.data ? `${chats.data.whitelist.length} / ${chats.data.blacklist.length}` : "..."
              }
              mono
            />
            <GlanceItem
              label="uptime"
              href="/settings/"
              value={runtime.data ? uptime(runtime.data.uptime_s) : "..."}
              mono
            />
          </dl>
        </Card>

        <Card title="activity">
          <ActivityFeed events={events} />
        </Card>
      </div>
    </div>
  );
}

function GlanceItem({
  label,
  value,
  href,
  mono = false,
}: {
  label: string;
  value: string;
  href: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="label">{label}</dt>
      <dd className="mt-1 truncate">
        <Link
          href={href}
          className={`text-text-1 transition-colors duration-150 hover:text-accent ${
            mono ? "mono text-sm" : ""
          }`}
        >
          {value}
        </Link>
      </dd>
    </div>
  );
}

function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const ordered = useMemo(() => events.slice(-100), [events]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest" });
  }, [ordered.length]);

  if (ordered.length === 0) {
    return <EmptyState text="no activity yet. incoming messages and replies will show up here." />;
  }

  return (
    <div className="max-h-[45vh] overflow-y-auto pr-1">
      <ul className="flex flex-col">
        {ordered.map((e) => {
          const { icon: Icon, className } = KIND_STYLE[e.kind] ?? KIND_STYLE.info;
          return (
            <li
              key={e.id}
              className="flex items-start gap-2.5 border-b border-line-1 py-1.5 last:border-b-0"
            >
              <Icon size={14} strokeWidth={1.5} className={`mt-0.5 shrink-0 ${className}`} />
              <span className="mono min-w-[64px] text-xs text-text-3">{timeOf(e.ts)}</span>
              <span className="mono min-w-0 flex-1 truncate text-xs text-text-2">{e.text}</span>
            </li>
          );
        })}
      </ul>
      <div ref={bottomRef} />
    </div>
  );
}
