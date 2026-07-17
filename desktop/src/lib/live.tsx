"use client";

// one sse connection for the whole app: activity events + runtime refresh

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { API_BASE } from "./api";
import { keys } from "./queries";
import type { ActivityEvent, Runtime } from "./types";

const MAX_EVENTS = 200;

interface LiveState {
  events: ActivityEvent[];
  connected: boolean;
}

const LiveContext = createContext<LiveState>({ events: [], connected: false });

export function useLive(): LiveState {
  return useContext(LiveContext);
}

export function LiveProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let delay = 500;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      source = new EventSource(`${API_BASE}/runtime/events`);

      source.onopen = () => {
        delay = 500;
        setConnected(true);
      };

      source.addEventListener("activity", (e) => {
        const event = JSON.parse((e as MessageEvent).data) as ActivityEvent;
        if (seen.current.has(event.id)) return;
        seen.current.add(event.id);
        setEvents((prev) => {
          const next = [...prev, event];
          return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
        });
      });

      source.addEventListener("runtime", (e) => {
        const runtime = JSON.parse((e as MessageEvent).data) as Runtime;
        qc.setQueryData(keys.runtime, runtime);
      });

      source.onerror = () => {
        setConnected(false);
        source?.close();
        retry = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 8000);
      };
    };

    connect();
    return () => {
      stopped = true;
      source?.close();
      if (retry) clearTimeout(retry);
    };
  }, [qc]);

  return <LiveContext.Provider value={{ events, connected }}>{children}</LiveContext.Provider>;
}
