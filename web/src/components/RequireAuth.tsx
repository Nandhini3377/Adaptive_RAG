"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";

import { getToken } from "@/lib/api";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange); // logins/logouts in other tabs
  return () => window.removeEventListener("storage", onChange);
}

/** Render children only for a logged-in user; otherwise go to the login page. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  // The token lives in localStorage, which only exists in the browser: null on the server
  const loggedIn = useSyncExternalStore(
    subscribe,
    () => getToken() !== null,
    () => null,
  );

  useEffect(() => {
    if (loggedIn === false) router.replace("/login");
  }, [loggedIn, router]);

  if (!loggedIn) return <p className="p-8 text-sm text-ink-soft">Loading…</p>;
  return <>{children}</>;
}
