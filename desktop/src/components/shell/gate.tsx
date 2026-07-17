"use client";

// routes the whole app by backend state: splash -> setup -> login -> shell

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuthStatus, useRuntime } from "@/lib/queries";
import { Spinner } from "@/components/ui/spinner";
import { Shell } from "./shell";

const FULLSCREEN_ROUTES = ["/setup", "/login"];

export function AppGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const runtime = useRuntime();
  // poll auth while a login flow is in progress so qr scans land without sse
  const auth = useAuthStatus(1500);

  const authState = auth.data?.state;
  const needsSetup = authState === "no_credentials";
  const needsLogin =
    authState === "unauthorized" ||
    authState === "qr_pending" ||
    authState === "password_needed" ||
    authState === "connecting";

  useEffect(() => {
    if (!authState) return;
    if (needsSetup && pathname !== "/setup/") router.replace("/setup/");
    else if (!needsSetup && needsLogin && pathname !== "/login/") router.replace("/login/");
    else if (authState === "authorized" && FULLSCREEN_ROUTES.some((r) => pathname.startsWith(r))) {
      router.replace("/");
    }
  }, [authState, needsSetup, needsLogin, pathname, router]);

  // backend unreachable: keep retrying quietly
  if (runtime.isError && auth.isError) {
    return (
      <Splash>
        <Spinner size={18} />
        <p className="text-sm text-text-2">connecting to core</p>
        <p className="max-w-xs text-center text-xs text-text-3">
          start it with <span className="mono text-text-2">python -m tgai</span> if it is not
          running
        </p>
      </Splash>
    );
  }

  if (!authState) {
    return (
      <Splash>
        <Spinner size={18} />
      </Splash>
    );
  }

  if (FULLSCREEN_ROUTES.some((r) => pathname.startsWith(r))) {
    return <main className="min-h-screen">{children}</main>;
  }

  return <Shell>{children}</Shell>;
}

function Splash({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg-0">
      {children}
    </div>
  );
}
