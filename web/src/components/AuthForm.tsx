"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { api, setToken } from "@/lib/api";

import { GraphIcon, HashIcon, LayersIcon, Logo } from "./icons";
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
    <div className="fixed inset-0 grid overflow-y-auto bg-page lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel: fixed colours so it looks the same in light and dark */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-[#312e81] via-[#4338ca] to-[#7c3aed] p-12 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.12]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
            backgroundSize: "44px 44px",
          }}
        />
        <div className="relative flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="rounded-[10px] ring-1 ring-white/30">
            <Logo />
          </span>
          Adaptive RAG
        </div>

        <div className="relative max-w-md">
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">
            The right search for every document, and every question.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-white/75">
            Each upload is scanned and indexed the way that suits it. Each question is routed to
            the best index available, and every answer explains how it was found.
          </p>
          <ul className="mt-9 space-y-3">
            <Feature icon={<LayersIcon width={18} height={18} />} title="Vector search">
              Finds passages by meaning, for facts and policies.
            </Feature>
            <Feature icon={<HashIcon width={18} height={18} />} title="Keyword search">
              Matches exact terms, IDs and error codes.
            </Feature>
            <Feature icon={<GraphIcon width={18} height={18} />} title="Knowledge graph">
              Follows how things connect and depend on each other.
            </Feature>
          </ul>
        </div>

        <p className="relative text-sm text-white/60">Answers come with citations and a full explanation.</p>
      </div>

      <div className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-2.5 font-semibold tracking-tight text-ink lg:hidden">
            <Logo />
            Adaptive RAG
          </div>
          <h1 className="mt-8 text-3xl font-semibold tracking-tight text-ink lg:mt-0">
            {isRegister ? "Create an account" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            {isRegister ? "Start uploading documents in a minute." : "Log in to your documents and questions."}
          </p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block text-sm">
              <span className="font-medium text-ink">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="field mt-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium text-ink">Password</span>
              {isRegister && <span className="ml-1.5 text-xs text-ink-soft">at least 8 characters</span>}
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                autoComplete={isRegister ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field mt-1.5"
              />
            </label>
            <ErrorBox message={error} />
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Please wait…" : isRegister ? "Create account" : "Log in"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-ink-soft">
            {isRegister ? "Already have an account? " : "New here? "}
            <Link href={isRegister ? "/login" : "/register"} className="font-medium text-accent hover:underline">
              {isRegister ? "Log in" : "Create an account"}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-3.5 rounded-2xl bg-white/10 px-4 py-3.5 ring-1 ring-white/15 backdrop-blur-sm">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15">{icon}</span>
      <span>
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-sm text-white/70">{children}</span>
      </span>
    </li>
  );
}
