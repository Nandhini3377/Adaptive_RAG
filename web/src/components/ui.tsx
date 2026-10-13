// Small presentational building blocks shared by every page.

import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { ArrowLeftIcon } from "./icons";

export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-line/70 bg-surface shadow-card ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-3 px-6 pt-5">
          {title && <h2 className="font-semibold tracking-tight text-ink">{title}</h2>}
          {action}
        </div>
      )}
      <div className={title || action ? "px-6 pb-6 pt-4" : "p-6"}>{children}</div>
    </section>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
  size?: "sm" | "md";
};

export function Button({ variant = "primary", size = "md", className = "", ...props }: ButtonProps) {
  const styles = {
    primary: "bg-accent text-on-accent shadow-sm shadow-accent/30 hover:bg-accent-strong",
    secondary: "border border-line bg-surface text-ink hover:bg-muted",
    danger: "border border-danger/30 text-danger hover:bg-danger/10",
  }[variant];
  const sizes = { sm: "h-8 px-3.5 text-xs", md: "h-10 px-4.5 text-sm" }[size];
  return (
    <button
      className={`inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${sizes} ${styles} ${className}`}
      {...props}
    />
  );
}

export function Badge({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "good" | "warn" | "bad";
  dot?: boolean;
}) {
  const styles = {
    neutral: "bg-muted text-ink-soft",
    accent: "bg-accent/10 text-accent",
    good: "bg-good/12 text-good",
    warn: "bg-warn/15 text-warn",
    bad: "bg-danger/12 text-danger",
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={value}>
      <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${value}%` }} />
    </div>
  );
}

export function ErrorBox({ message, className = "" }: { message: string | null; className?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className={`rounded-xl border border-danger/30 bg-danger/8 px-3.5 py-2.5 text-sm text-danger ${className}`}>
      {message}
    </p>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-line/70 bg-surface px-4 py-3.5" title={hint}>
      <div className="truncate text-xs text-ink-soft">{label}</div>
      <div className="mt-1 text-xl font-semibold leading-tight tracking-tight tabular-nums text-ink">{value}</div>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
  back,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <div className="mb-8">
      {back && (
        <Link
          href={back.href}
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-ink-soft transition-colors hover:text-ink"
        >
          <ArrowLeftIcon width={14} height={14} />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <h1 className="break-words text-3xl font-semibold tracking-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-ink-soft">{subtitle}</p>}
        </div>
        {action}
      </div>
    </div>
  );
}

export function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-line border-t-accent"
      aria-hidden="true"
    />
  );
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <p className="flex items-center gap-2.5 py-2 text-sm text-ink-soft" role="status">
      <Spinner />
      {text}
    </p>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line bg-surface/60 px-6 py-14 text-center">
      {icon && (
        <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent">
          {icon}
        </span>
      )}
      <h2 className="font-semibold tracking-tight text-ink">{title}</h2>
      {children && <p className="mt-1 max-w-md text-sm leading-relaxed text-ink-soft">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Small uppercase heading for a group inside a card. */
export function SectionLabel({ children }: { children: ReactNode }) {
  return <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-ink-soft">{children}</h3>;
}

/** A headline number with an icon, for the row of totals at the top of a page. */
export function MetricTile({
  icon,
  label,
  value,
  tone = "accent",
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  tone?: "accent" | "good" | "warn" | "neutral";
}) {
  const tones = {
    accent: "bg-accent/10 text-accent",
    good: "bg-good/12 text-good",
    warn: "bg-warn/15 text-warn",
    neutral: "bg-muted text-ink-soft",
  }[tone];
  return (
    <div className="flex items-center gap-3.5 rounded-2xl border border-line/70 bg-surface p-4 shadow-card">
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tones}`}>{icon}</span>
      <div className="min-w-0">
        <div className="text-2xl font-semibold leading-none tracking-tight tabular-nums text-ink">{value}</div>
        <div className="mt-1.5 truncate text-xs text-ink-soft">{label}</div>
      </div>
    </div>
  );
}

/** A circular gauge for a share between 0 and 1, with the percentage in the middle. */
export function Ring({ value, size = 56 }: { value: number | null | undefined; size?: number }) {
  const stroke = 6;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const share = value == null ? 0 : Math.min(Math.max(value, 0), 1);
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - share)}
        />
      </svg>
      <span className="absolute text-xs font-semibold tabular-nums text-ink">
        {value == null ? "—" : `${Math.round(share * 100)}%`}
      </span>
    </span>
  );
}

/** A labelled horizontal bar for a score between 0 and 1. */
export function Meter({ label, value, hint }: { label: string; value: number | null | undefined; hint?: string }) {
  const share = value == null ? 0 : Math.min(Math.max(value, 0), 1);
  return (
    <div className="rounded-xl border border-line/70 bg-surface px-4 py-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs text-ink-soft">{label}</span>
        <span className="text-base font-semibold tabular-nums text-ink">{value == null ? "—" : value.toFixed(2)}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-accent" style={{ width: `${share * 100}%` }} />
      </div>
      {hint && <p className="mt-2 text-xs leading-relaxed text-ink-soft">{hint}</p>}
    </div>
  );
}
