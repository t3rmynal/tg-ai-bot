"use client";

import { Plus, RefreshCw, Shuffle, X, Zap } from "lucide-react";
import { useState } from "react";

import {
  testProxy,
  useAddManualProxy,
  usePatchProxy,
  useProxy,
  useProxyList,
  useRefreshMullvad,
  useRemoveManualProxy,
  useRotateProxy,
} from "@/lib/queries";
import type { ProxyStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, PageHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Spinner } from "@/components/ui/spinner";
import { ToggleRow } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";

const ROTATIONS: { value: ProxyStatus["rotation"]; label: string }[] = [
  { value: "off", label: "off" },
  { value: "per_request", label: "every call" },
  { value: "per_n", label: "every n calls" },
];

export default function ProxyPage() {
  const proxy = useProxy();
  const patch = usePatchProxy();
  const rotate = useRotateProxy();
  const toast = useToast();
  const [testing, setTesting] = useState(false);

  const p = proxy.data;
  const setPatch = (body: Parameters<typeof patch.mutate>[0]) =>
    patch.mutate(body, { onError: (e) => toast(e.message, "danger") });

  const testActive = async () => {
    setTesting(true);
    try {
      const res = await testProxy("");
      if (res.ok) toast(`exit ${res.ip} ${res.country || ""}`.trim(), "ok");
      else toast(res.error ?? "test failed", "danger");
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow="outbound routing"
        title="proxy"
        index="05"
        status={<Badge tone={p?.enabled ? "accent" : "neutral"}>{p?.enabled ? "on" : "off"}</Badge>}
      />

      <div className="flex flex-col gap-4">
        <Card title="routing">
          <ToggleRow
            label="route ai traffic through a proxy"
            hint="provider calls go out through the pool below"
            checked={p?.enabled ?? false}
            onCheckedChange={(v) => setPatch({ enabled: v })}
          />
          <div className="border-t border-line-1 pt-3">
            <ToggleRow
              label="also route telegram"
              hint="applies at the next connect, reconnect to switch exit"
              checked={p?.apply_to_telegram ?? false}
              onCheckedChange={(v) => setPatch({ apply_to_telegram: v })}
            />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4">
            <Field label="source">
              <Segmented
                options={[
                  { value: "manual", label: "manual" },
                  { value: "mullvad", label: "mullvad" },
                ]}
                value={p?.mode}
                onChange={(m) => setPatch({ mode: m })}
              />
            </Field>
            <Field label="rotation">
              <Segmented
                options={ROTATIONS.map((r) => ({ value: r.value, label: r.label }))}
                value={p?.rotation}
                onChange={(rotation) => setPatch({ rotation })}
              />
            </Field>
          </div>

          {p?.rotation === "per_n" ? (
            <div className="mt-4 max-w-[200px]">
              <RotateEveryField value={p.rotate_every} onCommit={(v) => setPatch({ rotate_every: v })} />
            </div>
          ) : null}

          <div className="mt-4 flex items-center justify-between border-t border-line-1 pt-4">
            <p className="text-sm text-text-2">
              {p ? (
                <>
                  <span className="mono text-text-1">{p.pool_size}</span> proxies in the pool
                  {p.active ? (
                    <>
                      <span className="text-text-3"> / active </span>
                      <span className="mono text-accent">{p.active}</span>
                    </>
                  ) : null}
                </>
              ) : (
                "..."
              )}
            </p>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" disabled={!p?.active || testing} onClick={testActive}>
                {testing ? <Spinner size={12} /> : <Zap size={13} strokeWidth={1.5} />}
                test active
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={!p?.pool_size || rotate.isPending}
                onClick={() =>
                  rotate.mutate(undefined, {
                    onSuccess: (r) => toast(r.active ? `now ${r.active}` : "rotated", "ok"),
                    onError: (e) => toast(e.message, "danger"),
                  })
                }
              >
                <Shuffle size={13} strokeWidth={1.5} /> rotate now
              </Button>
            </div>
          </div>
        </Card>

        {p?.mode === "mullvad" ? <MullvadCard status={p} /> : <ManualCard />}
      </div>
    </div>
  );
}

function RotateEveryField({ value, onCommit }: { value: number; onCommit: (v: number) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <Field label="rotate every, calls" hint="1 to 1000">
      <Input
        inputMode="numeric"
        className="mono"
        value={draft ?? String(value)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft === null) return;
          const n = Math.max(1, Math.min(1000, Number(draft) || value));
          setDraft(null);
          if (n !== value) onCommit(n);
        }}
      />
    </Field>
  );
}

function ManualCard() {
  const list = useProxyList();
  const add = useAddManualProxy();
  const remove = useRemoveManualProxy();
  const toast = useToast();
  const [url, setUrl] = useState("");

  return (
    <Card
      title="manual proxies"
      actions={<span className="mono text-xs text-text-3">socks5, socks4, http</span>}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!url.trim()) return;
          add.mutate(url.trim(), {
            onSuccess: () => {
              setUrl("");
              toast("proxy added", "ok");
            },
            onError: (err) => toast(err.message, "danger"),
          });
        }}
        className="flex items-end gap-2"
      >
        <div className="min-w-0 flex-1">
          <Field label="add a proxy">
            <Input
              className="mono"
              placeholder="socks5://user:pass@host:1080"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </Field>
        </div>
        <Button type="submit" disabled={!url.trim() || add.isPending}>
          <Plus size={13} strokeWidth={1.5} /> add
        </Button>
      </form>

      <div className="mt-4">
        {!list.data?.manual.length ? (
          <EmptyState text="no manual proxies yet" />
        ) : (
          <ul className="-my-1 flex flex-col">
            {list.data.manual.map((m) => (
              <li
                key={m.index}
                className="group flex items-center justify-between gap-2 border-b border-line-1
                  py-2 last:border-b-0"
              >
                <span className="mono min-w-0 flex-1 truncate text-sm text-text-2">{m.masked}</span>
                <button
                  aria-label={`remove ${m.masked}`}
                  className="rounded-sm p-1 text-text-3 opacity-0 transition-all duration-150
                    group-hover:opacity-100 hover:bg-bg-3 hover:text-danger"
                  onClick={() =>
                    remove.mutate(m.index, { onError: (e) => toast(e.message, "danger") })
                  }
                >
                  <X size={13} strokeWidth={1.5} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function MullvadCard({ status }: { status: ProxyStatus }) {
  const refresh = useRefreshMullvad();
  const toast = useToast();
  const [country, setCountry] = useState(status.mullvad_country);

  return (
    <Card title="mullvad exits">
      <p className="mb-4 text-sm text-text-2">
        connect the mullvad app first, then pull the socks5 exit list. each call leaves through a
        different mullvad server while the tunnel is up.
      </p>
      <div className="flex items-end gap-2">
        <Field label="country code, two letters, blank for all">
          <Input
            className="mono w-40"
            maxLength={2}
            placeholder="se"
            value={country}
            onChange={(e) => setCountry(e.target.value.toLowerCase())}
          />
        </Field>
        <Button
          disabled={refresh.isPending}
          onClick={() =>
            refresh.mutate(country, {
              onSuccess: (r) => toast(`loaded ${r.count} exits`, "ok"),
              onError: (e) => toast(e.message, "danger"),
            })
          }
        >
          {refresh.isPending ? <Spinner size={12} /> : <RefreshCw size={13} strokeWidth={1.5} />}
          pull exits
        </Button>
      </div>

      <div className="mt-4 flex items-center gap-2 border-t border-line-1 pt-4">
        <span className="mono text-sm text-text-1">{status.mullvad_count}</span>
        <span className="text-sm text-text-3">exits loaded</span>
      </div>
    </Card>
  );
}
