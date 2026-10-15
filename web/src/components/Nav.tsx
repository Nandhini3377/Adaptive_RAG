"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, getToken, setToken } from "@/lib/api";

import { ChatIcon, FileIcon, FlaskIcon, Logo, LogoutIcon } from "./icons";

const LINKS = [
  { href: "/", label: "Documents", icon: FileIcon },
  { href: "/chat", label: "Ask", icon: ChatIcon },
  { href: "/lab", label: "Evaluation Lab", icon: FlaskIcon },
];

type Health = Awaited<ReturnType<typeof api.health>>;

/** The app frame: a sidebar on wide screens, a top bar on small ones. */
export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  // null = still checking, "down" = the API did not answer
  const [health, setHealth] = useState<Health | "down" | null>(null);
  const onAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register");

  useEffect(() => {
    if (onAuthPage || !getToken()) return;
    api
      .me()
      .then((user) => setEmail(user.email))
      .catch(() => setEmail(null));
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth("down"));
  }, [onAuthPage]);

  if (onAuthPage) return null;

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/documents") : pathname.startsWith(href);

  function logOut() {
    setToken(null);
    router.push("/login");
  }

  const up = health !== null && health !== "down";

  return (
    <div data-sidebar>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line/70 bg-surface lg:flex">
        <Link href="/" className="flex h-16 shrink-0 items-center gap-2.5 px-5 font-semibold tracking-tight text-ink">
          <Logo />
          Adaptive RAG
        </Link>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-soft">Workspace</p>
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={isActive(link.href) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                isActive(link.href)
                  ? "bg-accent/10 font-medium text-accent"
                  : "text-ink-soft hover:bg-muted hover:text-ink"
              }`}
            >
              <link.icon width={18} height={18} />
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="space-y-2 p-3">
          <div className="rounded-xl border border-line/70 bg-page/60 px-3.5 py-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-soft">System</p>
            <ul className="space-y-1.5 text-xs">
              <StatusRow
                name="API"
                state={health === null ? null : up}
                text={health === null ? "Checking…" : up ? "Online" : "Offline"}
              />
              <StatusRow
                name="LLM"
                state={up ? health.llm === "configured" : null}
                text={up ? (health.llm === "configured" ? "Configured" : "Missing key") : "—"}
              />
              <StatusRow
                name="Graph database"
                state={up ? health.neo4j === "up" : null}
                text={up ? (health.neo4j === "up" ? "Running" : "Stopped") : "—"}
              />
            </ul>
          </div>

          <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-xs font-semibold uppercase text-accent">
              {email?.[0] ?? "·"}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm text-ink" title={email ?? undefined}>
              {email ?? "Signed in"}
            </span>
            <button
              type="button"
              onClick={logOut}
              aria-label="Log out"
              title="Log out"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-muted hover:text-ink"
            >
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-line/60 bg-page/75 backdrop-blur-md lg:hidden">
        <nav className="flex h-14 items-center gap-3 px-4">
          <Link href="/" aria-label="Adaptive RAG" className="shrink-0">
            <Logo />
          </Link>
          <div className="flex flex-1 overflow-x-auto">
            <div className="flex items-center gap-0.5 rounded-full bg-muted p-1">
              {LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive(link.href) ? "page" : undefined}
                  className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm transition-colors ${
                    isActive(link.href) ? "bg-surface font-medium text-ink shadow-sm" : "text-ink-soft hover:text-ink"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={logOut}
            aria-label="Log out"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-soft transition-colors hover:bg-muted hover:text-ink"
          >
            <LogoutIcon />
          </button>
        </nav>
      </header>
    </div>
  );
}

/** One line of the system panel. `state` null means unknown (still checking, or the API is down). */
function StatusRow({ name, state, text }: { name: string; state: boolean | null; text: string }) {
  const dot = state === null ? "bg-line" : state ? "bg-good" : "bg-warn";
  return (
    <li className="flex items-center gap-2">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      <span className="flex-1 text-ink-soft">{name}</span>
      <span className="text-ink">{text}</span>
    </li>
  );
}
