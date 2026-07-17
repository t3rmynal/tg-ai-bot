"use client";

import { openUrl } from "@tauri-apps/plugin-opener";
import { ExternalLink, LogOut, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  useAuthStatus,
  useCheckUpdates,
  useLogout,
  usePatchSettings,
  useProviders,
  useSettings,
  useUpdates,
} from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { ToggleRow } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";

export default function SettingsPage() {
  const settings = useSettings();
  const patch = usePatchSettings();
  const auth = useAuthStatus();
  const providers = useProviders();
  const logout = useLogout();
  const toast = useToast();

  const b = settings.data?.behavior;
  const patchBehavior = (key: string, value: number | boolean) =>
    patch.mutate({ behavior: { [key]: value } }, { onError: (e) => toast(e.message, "danger") });

  const activeProvider = providers.data?.providers.find(
    (p) => p.name === providers.data?.active.name,
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Card title="reply behavior">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
          <NumberField
            label="response delay, s"
            hint="0 to 30"
            value={b?.response_delay}
            min={0}
            max={30}
            step={0.5}
            onCommit={(v) => patchBehavior("response_delay", v)}
          />
          <NumberField
            label="per chat cooldown, s"
            hint="0 to 120"
            value={b?.per_chat_cooldown}
            min={0}
            max={120}
            step={0.5}
            onCommit={(v) => patchBehavior("per_chat_cooldown", v)}
          />
          <NumberField
            label="history depth, msgs"
            hint="1 to 1000"
            value={b?.history_limit}
            min={1}
            max={1000}
            step={1}
            onCommit={(v) => patchBehavior("history_limit", Math.round(v))}
          />
          <NumberField
            label="max tokens"
            hint="1 to 4000"
            value={b?.ai_max_tokens}
            min={1}
            max={4000}
            step={50}
            onCommit={(v) => patchBehavior("ai_max_tokens", Math.round(v))}
          />
          <NumberField
            label="temperature"
            hint="0 to 2"
            value={b?.ai_temperature}
            min={0}
            max={2}
            step={0.05}
            onCommit={(v) => patchBehavior("ai_temperature", v)}
          />
          <Field label="bot name" hint="blank uses your account name">
            <BotNameInput
              value={settings.data?.bot_name ?? ""}
              onCommit={(v) => patch.mutate({ bot_name: v })}
            />
          </Field>
        </div>
        <div className="mt-2 border-t border-line-1 pt-1">
          <ToggleRow
            label="thinking mode"
            hint={
              activeProvider?.supports_thinking
                ? "the model reasons before answering, slower"
                : `${activeProvider?.label ?? "the active provider"} does not support it`
            }
            checked={b?.ai_thinking ?? false}
            onCheckedChange={(v) => patchBehavior("ai_thinking", v)}
            disabled={!activeProvider?.supports_thinking}
          />
        </div>
      </Card>

      <Card title="account">
        <div className="flex items-center justify-between gap-4">
          <div>
            {auth.data?.user ? (
              <>
                <p className="text-sm text-text-1">
                  {auth.data.user.first_name}
                  {auth.data.user.username ? (
                    <span className="mono ml-2 text-xs text-text-3">
                      @{auth.data.user.username}
                    </span>
                  ) : null}
                </p>
                <p className="mt-0.5 text-xs text-ok">signed in</p>
              </>
            ) : (
              <p className="text-sm text-text-3">not signed in</p>
            )}
          </div>
          {auth.data?.user ? (
            <Button
              variant="danger"
              size="sm"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              <LogOut size={13} strokeWidth={1.5} /> sign out
            </Button>
          ) : null}
        </div>
      </Card>

      <UpdatesCard />

      <Card title="data">
        <p className="text-xs leading-relaxed text-text-3">
          everything lives next to the core process: config.json holds settings and provider keys,
          histories.json holds chat memory, userbot.session holds the telegram session. delete
          those files to reset the bot completely.
        </p>
      </Card>
    </div>
  );
}

function UpdatesCard() {
  const updates = useUpdates();
  const check = useCheckUpdates();
  const info = check.data ?? updates.data;

  return (
    <Card
      title="updates"
      actions={
        <Button
          size="sm"
          variant="ghost"
          disabled={check.isPending}
          onClick={() => check.mutate()}
        >
          <RefreshCw size={13} strokeWidth={1.5} className={check.isPending ? "animate-spin" : ""} />
          check now
        </Button>
      }
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="mono text-sm text-text-1">v{info?.current ?? "..."}</p>
          {info?.update_available ? (
            <p className="mt-0.5 text-xs text-accent">v{info.latest} is out</p>
          ) : info?.error ? (
            <p className="mt-0.5 text-xs text-text-3">could not reach github: {info.error}</p>
          ) : info?.latest ? (
            <p className="mt-0.5 text-xs text-text-3">latest release is v{info.latest}, you are current</p>
          ) : (
            <p className="mt-0.5 text-xs text-text-3">no releases published yet</p>
          )}
        </div>
        {info?.update_available && info.url ? (
          <Button
            size="sm"
            onClick={() => openUrl(info.url).catch(() => window.open(info.url, "_blank"))}
          >
            open release <ExternalLink size={12} strokeWidth={1.5} />
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function NumberField({
  label,
  hint,
  value,
  min,
  max,
  step,
  onCommit,
}: {
  label: string;
  hint: string;
  value: number | undefined;
  min: number;
  max: number;
  step: number;
  onCommit: (v: number) => void;
}) {
  // draft only exists while the user is editing, otherwise show the server value
  const [draft, setDraft] = useState<string | null>(null);

  return (
    <Field label={label} hint={hint}>
      <Input
        inputMode="decimal"
        className="mono"
        value={draft ?? (value !== undefined ? String(value) : "")}
        step={step}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft === null) return;
          const n = Number(draft);
          setDraft(null);
          if (Number.isNaN(n) || value === undefined) return;
          const clamped = Math.max(min, Math.min(max, n));
          if (clamped !== value) onCommit(clamped);
        }}
      />
    </Field>
  );
}

function BotNameInput({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null);

  return (
    <Input
      value={draft ?? value}
      maxLength={30}
      placeholder="account name"
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft === null) return;
        setDraft(null);
        if (draft.trim() !== value) onCommit(draft.trim());
      }}
    />
  );
}
