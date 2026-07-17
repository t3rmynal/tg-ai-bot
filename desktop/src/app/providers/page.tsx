"use client";

import { openUrl } from "@tauri-apps/plugin-opener";
import { Check, ExternalLink, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  fetchLiveModels,
  useAddModel,
  useCreateProvider,
  useDeleteProvider,
  usePatchProvider,
  useProviders,
  useRefreshModels,
  useRemoveModel,
  useSetActive,
  useSetKey,
} from "@/lib/queries";
import type { Provider } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";

export default function ProvidersPage() {
  const providers = useProviders();
  const [selected, setSelected] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const list = providers.data?.providers ?? [];
  const activeName = providers.data?.active.name;
  const current = list.find((p) => p.name === (selected ?? activeName));

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-[240px_1fr] items-start gap-4">
      <Card
        title="providers"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setAddOpen(true)} aria-label="add provider">
            <Plus size={14} strokeWidth={1.5} />
          </Button>
        }
      >
        <ul className="-m-2 flex flex-col gap-0.5">
          {list.map((p) => {
            const isActive = p.name === activeName;
            const isSelected = p.name === current?.name;
            return (
              <li key={p.name}>
                <button
                  onClick={() => setSelected(p.name)}
                  className={`relative flex w-full items-center justify-between gap-2 rounded-md
                    px-2.5 py-2 text-left text-sm transition-colors duration-120 ${
                      isSelected ? "bg-accent-dim text-text-1" : "text-text-2 hover:bg-bg-3"
                    }`}
                >
                  {isSelected ? (
                    <span
                      aria-hidden
                      className="absolute top-2 bottom-2 left-0 w-px bg-accent
                        shadow-[0_0_6px_var(--color-line-glow)]"
                    />
                  ) : null}
                  <span className="min-w-0 truncate">{p.label}</span>
                  <span className="flex shrink-0 items-center gap-1">
                    {p.recommended ? <Badge tone="accent">rec</Badge> : null}
                    {isActive ? <Badge tone="ok">active</Badge> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      {current ? (
        <ProviderDetail key={current.name} provider={current} isActive={current.name === activeName} activeModel={providers.data?.active.model} />
      ) : (
        <Card>
          <EmptyState text="pick a provider on the left" />
        </Card>
      )}

      <AddProviderDialog open={addOpen} onOpenChange={setAddOpen} onCreated={setSelected} />
    </div>
  );
}

function ProviderDetail({
  provider,
  isActive,
  activeModel,
}: {
  provider: Provider;
  isActive: boolean;
  activeModel?: string;
}) {
  const toast = useToast();
  const setActive = useSetActive();
  const setKey = useSetKey();
  const patch = usePatchProvider();
  const remove = useDeleteProvider();
  const addModel = useAddModel();
  const removeModel = useRemoveModel();

  const [keyOpen, setKeyOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [rpm, setRpm] = useState(String(provider.rpm));
  const [baseUrl, setBaseUrl] = useState(provider.base_url);

  const editableUrl = !provider.builtin || provider.name === "openai_compat" || provider.name === "ollama";

  return (
    <div className="flex flex-col gap-4">
      <Card
        title={provider.label}
        actions={
          <div className="flex items-center gap-2">
            {provider.signup && provider.signup.startsWith("http") ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => openUrl(provider.signup).catch(() => window.open(provider.signup))}
              >
                get a key <ExternalLink size={12} strokeWidth={1.5} />
              </Button>
            ) : null}
            {!provider.builtin ? (
              <Button
                size="sm"
                variant="danger"
                disabled={isActive || remove.isPending}
                onClick={() =>
                  remove.mutate(provider.name, {
                    onError: (e) => toast(e.message, "danger"),
                  })
                }
              >
                <Trash2 size={13} strokeWidth={1.5} /> remove
              </Button>
            ) : null}
            <Button
              size="sm"
              variant={isActive ? "outline" : "primary"}
              disabled={isActive || setActive.isPending}
              onClick={() =>
                setActive.mutate(
                  { name: provider.name },
                  { onError: (e) => toast(e.message, "danger") },
                )
              }
            >
              {isActive ? "active" : "use this provider"}
            </Button>
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="api key">
            <div className="flex items-center gap-2">
              <Input
                readOnly
                value={
                  provider.key_set
                    ? provider.api_key_masked
                    : provider.needs_key
                      ? "no key set"
                      : "not needed"
                }
                className={`mono ${provider.key_set || !provider.needs_key ? "" : "text-danger"}`}
              />
              <Button size="sm" onClick={() => setKeyOpen(true)}>
                set
              </Button>
            </div>
          </Field>
          <Field label="requests per minute" hint="calls are spaced to stay under this cap">
            <Input
              inputMode="numeric"
              className="mono"
              value={rpm}
              onChange={(e) => setRpm(e.target.value)}
              onBlur={() => {
                const value = Math.max(1, Math.min(10000, Number(rpm) || provider.rpm));
                setRpm(String(value));
                if (value !== provider.rpm) patch.mutate({ name: provider.name, rpm: value });
              }}
            />
          </Field>
          {editableUrl ? (
            <Field label="base url" hint="openai dialect, /chat/completions is appended">
              <Input
                className="mono col-span-2"
                value={baseUrl}
                placeholder="https://api.example.com/v1"
                onChange={(e) => setBaseUrl(e.target.value)}
                onBlur={() => {
                  const value = baseUrl.trim().replace(/\/+$/, "");
                  if (value !== provider.base_url)
                    patch.mutate({ name: provider.name, base_url: value });
                }}
              />
            </Field>
          ) : null}
        </div>
      </Card>

      <Card
        title="models"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setPickerOpen(true)}>
            <Plus size={14} strokeWidth={1.5} /> add
          </Button>
        }
      >
        {provider.models.length === 0 ? (
          <EmptyState
            text="no models yet. fetch the live list from the provider or add one by hand."
            action={
              <Button size="sm" onClick={() => setPickerOpen(true)}>
                add models
              </Button>
            }
          />
        ) : (
          <ul className="-my-1 flex flex-col">
            {provider.models.map((m) => {
              const isActiveModel = isActive && m === activeModel;
              return (
                <li
                  key={m}
                  className="group flex items-center justify-between gap-2 border-b border-line-1
                    py-1.5 last:border-b-0"
                >
                  <button
                    className={`mono min-w-0 flex-1 truncate text-left text-sm transition-colors
                      duration-120 ${
                        isActiveModel ? "text-accent" : "text-text-2 hover:text-text-1"
                      }`}
                    title={isActiveModel ? "active model" : "make active"}
                    onClick={() =>
                      setActive.mutate(
                        { name: provider.name, model: m },
                        { onError: (e) => toast(e.message, "danger") },
                      )
                    }
                  >
                    {isActiveModel ? <Check size={12} className="mr-1.5 inline" /> : null}
                    {m}
                  </button>
                  <button
                    aria-label={`remove ${m}`}
                    className="rounded-sm p-1 text-text-3 opacity-0 transition-all duration-120
                      group-hover:opacity-100 hover:bg-bg-3 hover:text-danger"
                    onClick={() =>
                      removeModel.mutate(
                        { name: provider.name, model: m },
                        { onError: (e) => toast(e.message, "danger") },
                      )
                    }
                  >
                    <X size={13} strokeWidth={1.5} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <KeyDialog provider={provider} open={keyOpen} onOpenChange={setKeyOpen} onSave={(key) => {
        setKey.mutate(
          { name: provider.name, api_key: key },
          {
            onSuccess: () => {
              setKeyOpen(false);
              toast("key saved", "ok");
            },
            onError: (e) => toast(e.message, "danger"),
          },
        );
      }} />

      <ModelPickerDialog
        provider={provider}
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onAdd={(model) =>
          addModel.mutate(
            { name: provider.name, model },
            { onError: (e) => toast(e.message, "danger") },
          )
        }
      />
    </div>
  );
}

function KeyDialog({
  provider,
  open,
  onOpenChange,
  onSave,
}: {
  provider: Provider;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSave: (key: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`api key for ${provider.label}`}>
      <KeyForm provider={provider} onCancel={() => onOpenChange(false)} onSave={onSave} />
    </Dialog>
  );
}

function KeyForm({
  provider,
  onCancel,
  onSave,
}: {
  provider: Provider;
  onCancel: () => void;
  onSave: (key: string) => void;
}) {
  const [key, setKeyValue] = useState("");

  return (
    <form
        onSubmit={(e) => {
          e.preventDefault();
          if (key.trim()) onSave(key.trim());
        }}
        className="flex flex-col gap-4"
      >
        <Field label="key" hint="stored in the local config file, shown masked afterwards">
          <Input
            type="password"
            autoFocus
            className="mono"
            placeholder={provider.key_hint}
            value={key}
            onChange={(e) => setKeyValue(e.target.value)}
          />
        </Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          cancel
        </Button>
        <Button type="submit" variant="primary" disabled={!key.trim()}>
          save key
        </Button>
      </div>
    </form>
  );
}

function ModelPickerDialog({
  provider,
  open,
  onOpenChange,
  onAdd,
}: {
  provider: Provider;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onAdd: (model: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`models from ${provider.label}`} wide>
      {/* body unmounts with the dialog, so fetch state resets on close */}
      <ModelPickerBody provider={provider} onAdd={onAdd} onClose={() => onOpenChange(false)} />
    </Dialog>
  );
}

function ModelPickerBody({
  provider,
  onAdd,
  onClose,
}: {
  provider: Provider;
  onAdd: (model: string) => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const refresh = useRefreshModels();
  const [live, setLive] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [manual, setManual] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchLiveModels(provider.name)
      .then((res) => {
        if (cancelled) return;
        if (res.source === "live") setLive(res.models);
        else setError(res.error ?? "provider did not return a model list");
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [provider.name]);

  const filtered = useMemo(() => {
    if (!live) return [];
    const q = filter.trim().toLowerCase();
    const known = new Set(provider.models);
    return live.filter((m) => !known.has(m) && (!q || m.toLowerCase().includes(q)));
  }, [live, filter, provider.models]);

  return (
      <div className="flex flex-col gap-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-text-2">
            <Spinner size={13} /> fetching the live model list
          </div>
        ) : live ? (
          <>
            <div className="flex items-center gap-2">
              <Input
                placeholder="filter models"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <Button
                size="sm"
                variant="ghost"
                disabled={refresh.isPending}
                onClick={() =>
                  refresh.mutate(provider.name, {
                    onSuccess: (res) => {
                      toast(`saved ${res.added.length} new models`, "ok");
                      onClose();
                    },
                    onError: (e) => toast(e.message, "danger"),
                  })
                }
                title="merge the whole live list into the provider"
              >
                <RefreshCw size={13} strokeWidth={1.5} /> save all
              </Button>
            </div>
            <ul className="max-h-72 overflow-y-auto rounded-sm border border-line-1">
              {filtered.length === 0 ? (
                <li className="p-3 text-sm text-text-3">nothing new matches</li>
              ) : (
                filtered.map((m) => (
                  <li key={m} className="border-b border-line-1 last:border-b-0">
                    <button
                      className="mono flex w-full items-center justify-between px-3 py-1.5
                        text-left text-xs text-text-2 transition-colors duration-120
                        hover:bg-bg-3 hover:text-text-1"
                      onClick={() => onAdd(m)}
                    >
                      {m}
                      <Plus size={12} strokeWidth={1.5} className="shrink-0 text-text-3" />
                    </button>
                  </li>
                ))
              )}
            </ul>
          </>
        ) : (
          <p className="text-sm text-warn">
            could not fetch models from the provider{error ? `: ${error}` : ""}. add one by hand
            below.
          </p>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (manual.trim()) {
              onAdd(manual.trim());
              setManual("");
            }
          }}
          className="flex items-end gap-2"
        >
          <Field label="add by id">
            <Input
              className="mono w-72"
              placeholder="vendor/model-name"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={!manual.trim()}>
            add
          </Button>
        </form>
      </div>
  );
}

function AddProviderDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (name: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="add a provider">
      <AddProviderForm
        onCancel={() => onOpenChange(false)}
        onCreated={(name) => {
          onCreated(name);
          onOpenChange(false);
        }}
      />
    </Dialog>
  );
}

function AddProviderForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (name: string) => void;
}) {
  const toast = useToast();
  const create = useCreateProvider();
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");

  const nameValid = /^[a-z0-9_-]+$/.test(name);
  const canSubmit = nameValid && label.trim() && baseUrl.trim();

  return (
    <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!canSubmit) return;
          create.mutate(
            { name, label: label.trim(), base_url: baseUrl.trim(), api_key: apiKey.trim() },
            {
              onSuccess: () => {
                onCreated(name);
                toast("provider added", "ok");
              },
              onError: (e) => toast(e.message, "danger"),
            },
          );
        }}
        className="flex flex-col gap-4"
      >
        <p className="text-sm text-text-2">
          any openai compatible endpoint works: the bot calls base url + /chat/completions with a
          bearer key.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="id" hint={name && !nameValid ? "lowercase letters, digits, - _" : undefined}>
            <Input className="mono" value={name} onChange={(e) => setName(e.target.value)} placeholder="myapi" />
          </Field>
          <Field label="label">
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="My API" />
          </Field>
        </div>
        <Field label="base url">
          <Input
            className="mono"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.example.com/v1"
          />
        </Field>
        <Field label="api key (optional now)">
          <Input
            type="password"
            className="mono"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>
            cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!canSubmit || create.isPending}>
            add provider
          </Button>
        </div>
      </form>
  );
}
