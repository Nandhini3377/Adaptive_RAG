"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { api, setToken } from "@/lib/api";

import { Button, ErrorBox } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isRegister) await api.register(email, password);
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-12 max-w-sm">
      <h1 className="text-xl font-semibold text-ink">{isRegister ? "Create an account" : "Log in"}</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Adaptive RAG picks the right search strategy for each document you upload.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-4 rounded-xl border border-line bg-surface p-5">
        <label className="block text-sm">
          <span className="text-ink-soft">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-page px-3 py-2 text-ink outline-none focus:border-accent"
          />
        </label>
        <label className="block text-sm">
          <span className="text-ink-soft">Password {isRegister && "(at least 8 characters)"}</span>
          <input
            type="password"
            required
            minLength={8}
            maxLength={72}
            autoComplete={isRegister ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-page px-3 py-2 text-ink outline-none focus:border-accent"
          />
        </label>
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Please wait…" : isRegister ? "Create account" : "Log in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-soft">
        {isRegister ? "Already have an account? " : "New here? "}
        <Link href={isRegister ? "/login" : "/register"} className="text-accent hover:underline">
          {isRegister ? "Log in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
