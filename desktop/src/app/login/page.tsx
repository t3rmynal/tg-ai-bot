"use client";

import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef, useState } from "react";

import { useAuthStatus, useBeginQr, useSubmitPassword } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

export default function LoginPage() {
  const auth = useAuthStatus(1200);
  const beginQr = useBeginQr();
  const startedRef = useRef(false);

  const state = auth.data?.state;
  const qr = auth.data?.qr;

  // kick off the first qr as soon as we are connectable
  useEffect(() => {
    if (state === "unauthorized" && !startedRef.current) {
      startedRef.current = true;
      beginQr.mutate();
    }
  }, [state, beginQr]);

  // refresh when the code expires
  useEffect(() => {
    if (state !== "qr_pending" || !qr?.expires_at) return;
    const ms = new Date(qr.expires_at).getTime() - Date.now();
    const timer = setTimeout(() => beginQr.mutate(), Math.max(500, ms + 250));
    return () => clearTimeout(timer);
  }, [state, qr?.expires_at, beginQr]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-0 p-6">
      <div className="w-full max-w-sm rounded-lg border border-line-2 bg-bg-1 p-6">
        <h1 className="text-xl font-medium text-text-1">sign in to telegram</h1>

        {state === "password_needed" ? (
          <TwoFactorForm />
        ) : (
          <>
            <p className="mt-2 text-sm text-text-2">
              open telegram on your phone: settings, devices, link desktop device. then point the
              camera here.
            </p>
            <div className="mt-5 flex flex-col items-center gap-4">
              <div className="rounded-md bg-bg-2 p-4">
                {qr?.url ? (
                  <QRCodeSVG
                    value={qr.url}
                    size={232}
                    bgColor="#151a24"
                    fgColor="#e8edf4"
                    marginSize={1}
                  />
                ) : (
                  <div className="flex size-[232px] items-center justify-center">
                    <Spinner size={20} />
                  </div>
                )}
              </div>
              {qr?.expires_at ? <QrCountdown expiresAt={qr.expires_at} /> : null}
              <p className="text-xs text-text-3">the code refreshes itself about every 30s</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function QrCountdown({ expiresAt }: { expiresAt: string }) {
  const [fraction, setFraction] = useState(1);

  useEffect(() => {
    const end = new Date(expiresAt).getTime();
    const total = 30_000;
    const tick = () => setFraction(Math.max(0, Math.min(1, (end - Date.now()) / total)));
    tick();
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [expiresAt]);

  return (
    <div aria-hidden className="h-px w-[232px] bg-line-2">
      <div
        className="h-px bg-accent shadow-[0_0_6px_var(--color-line-glow)] transition-[width]"
        style={{ width: `${fraction * 100}%` }}
      />
    </div>
  );
}

function TwoFactorForm() {
  const submit = useSubmitPassword();
  const [password, setPassword] = useState("");

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password) submit.mutate(password);
  };

  return (
    <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-4">
      <p className="text-sm text-text-2">
        this account has two step verification. enter the cloud password to finish.
      </p>
      <Field label="cloud password">
        <Input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
        />
      </Field>
      {submit.isError ? <p className="text-xs text-danger">wrong password, try again</p> : null}
      <Button type="submit" variant="primary" disabled={!password || submit.isPending}>
        {submit.isPending ? <Spinner size={12} /> : null}
        sign in
      </Button>
    </form>
  );
}
