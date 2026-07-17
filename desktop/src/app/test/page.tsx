"use client";

import { SendHorizonal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useRuntime, useTestChat } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

interface Bubble {
  role: "user" | "assistant";
  content: string;
  latency_ms?: number;
}

export default function TestChatPage() {
  const runtime = useRuntime();
  const testChat = useTestChat();
  const [thread, setThread] = useState<Bubble[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [thread.length, testChat.isPending]);

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const message = draft.trim();
    if (!message || testChat.isPending) return;
    setError(null);
    setDraft("");
    const history = thread.map(({ role, content }) => ({ role, content }));
    setThread((prev) => [...prev, { role: "user", content: message }]);
    testChat.mutate(
      { message, history },
      {
        onSuccess: (res) =>
          setThread((prev) => [
            ...prev,
            { role: "assistant", content: res.reply, latency_ms: res.latency_ms },
          ]),
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-96px)] max-w-3xl flex-col gap-4">
      <Card
        title={`testing ${runtime.data?.persona ?? "..."} on ${runtime.data?.model ?? "..."}`}
        actions={
          thread.length > 0 ? (
            <Button size="sm" variant="ghost" onClick={() => setThread([])}>
              clear
            </Button>
          ) : undefined
        }
        className="flex min-h-0 flex-1 flex-col [&>div]:flex [&>div]:min-h-0 [&>div]:flex-1 [&>div]:flex-col"
      >
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {thread.length === 0 ? (
            <EmptyState text="say something to try the current persona and model. nothing here touches telegram or the bot memory." />
          ) : (
            thread.map((b, i) => (
              <div
                key={i}
                className={`max-w-[80%] rounded-md px-3 py-2 text-sm leading-relaxed ${
                  b.role === "user"
                    ? "self-end bg-accent-dim text-text-1"
                    : "self-start border border-line-1 bg-bg-2 text-text-1"
                }`}
              >
                <p className="whitespace-pre-wrap">{b.content}</p>
                {b.latency_ms !== undefined ? (
                  <p className="mono mt-1 text-right text-[10px] text-text-3">{b.latency_ms}ms</p>
                ) : null}
              </div>
            ))
          )}
          {testChat.isPending ? (
            <div className="flex items-center gap-2 self-start rounded-md border border-line-1 bg-bg-2 px-3 py-2">
              <Spinner size={12} />
              <span className="text-xs text-text-3">thinking</span>
            </div>
          ) : null}
          {error ? <p className="self-start text-xs text-danger">{error}</p> : null}
          <div ref={bottomRef} />
        </div>
        <form onSubmit={send} className="mt-3 flex shrink-0 items-center gap-2 border-t border-line-1 pt-3">
          <Input
            autoFocus
            placeholder="message"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button type="submit" variant="primary" disabled={!draft.trim() || testChat.isPending} aria-label="send">
            <SendHorizonal size={14} strokeWidth={1.5} />
          </Button>
        </form>
      </Card>
    </div>
  );
}
