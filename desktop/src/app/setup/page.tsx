"use client";

// first run: telegram api credentials. provider and persona live in the main app

import { openUrl } from "@tauri-apps/plugin-opener";
import { useState } from "react";

import { useSetCredentials } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

function openExternal(url: string) {
  openUrl(url).catch(() => window.open(url, "_blank"));
}

export default function SetupPage() {
  const setCredentials = useSetCredentials();
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");

  const idValid = /^\d+$/.test(apiId.trim());
  const canSubmit = idValid && apiHash.trim().length > 0;

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setCredentials.mutate({ api_id: Number(apiId.trim()), api_hash: apiHash.trim() });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-0 p-6">
      <div className="w-full max-w-sm rounded-lg border border-line-2 bg-bg-1 p-6">
        <p className="mono text-xs tracking-wide text-text-3">first run</p>
        <h1 className="mt-1 text-xl font-medium text-text-1">connect your telegram app keys</h1>
        <p className="mt-2 text-sm text-text-2">
          the bot signs in as you, so it needs your own api pair from{" "}
          <button
            type="button"
            className="text-accent underline-offset-2 hover:underline"
            onClick={() => openExternal("https://my.telegram.org/apps")}
          >
            my.telegram.org/apps
          </button>
          . keys stay in a local config file.
        </p>

        <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4">
          <Field label="api_id" hint={apiId && !idValid ? "digits only" : undefined}>
            <Input
              inputMode="numeric"
              autoFocus
              value={apiId}
              onChange={(e) => setApiId(e.target.value)}
              placeholder="1234567"
              className="mono"
            />
          </Field>
          <Field label="api_hash">
            <Input
              value={apiHash}
              onChange={(e) => setApiHash(e.target.value)}
              placeholder="0123456789abcdef0123456789abcdef"
              className="mono"
            />
          </Field>
          {setCredentials.isError ? (
            <p className="text-xs text-danger">could not save credentials, check the values</p>
          ) : null}
          <Button type="submit" variant="primary" disabled={!canSubmit || setCredentials.isPending}>
            {setCredentials.isPending ? <Spinner size={12} /> : null}
            continue to sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
