"use client";

import { useEffect, useEffectEvent } from "react";

/** Run `task` once when the component mounts (e.g. the first data load). */
export function useOnMount(task: () => void | Promise<void>) {
  const run = useEffectEvent(task);
  useEffect(() => {
    void run();
  }, []);
}

/** Call `task` every `intervalMs` while `active` is true (for background job status). */
export function usePolling(task: () => void | Promise<void>, intervalMs: number, active: boolean) {
  const run = useEffectEvent(task);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void run(), intervalMs);
    return () => clearInterval(timer);
  }, [active, intervalMs]);
}
