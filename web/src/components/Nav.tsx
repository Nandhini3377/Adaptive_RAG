"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { setToken } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Documents" },
  { href: "/chat", label: "Ask" },
  { href: "/eval", label: "Evaluation Lab" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  if (pathname.startsWith("/login") || pathname.startsWith("/register")) return null;

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/documents") : pathname.startsWith(href);

  return (
    <header className="border-b border-line bg-surface">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="font-semibold text-ink">
          Adaptive RAG
        </Link>
        <div className="flex flex-1 flex-wrap gap-1">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-md px-3 py-1.5 text-sm ${
                isActive(link.href) ? "bg-muted font-medium text-ink" : "text-ink-soft hover:text-ink"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <button
          type="button"
          className="text-sm text-ink-soft hover:text-ink"
          onClick={() => {
            setToken(null);
            router.push("/login");
          }}
        >
          Log out
        </button>
      </nav>
    </header>
  );
}
