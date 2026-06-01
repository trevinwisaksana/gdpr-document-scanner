"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, ScanSearch, Lock, ArrowRight } from "lucide-react";
import { useSession } from "@/lib/session";
import { Button, Spinner } from "@/components/ui";

interface DemoChip {
  username: string;
  password: string;
  label: string;
  role: string;
}

const DEMO_CHIPS: DemoChip[] = [
  { username: "admin", password: "admin", label: "Administrator (DPO)", role: "Full org-wide oversight" },
  { username: "user", password: "user", label: "Employee", role: "Your own flagged files" },
  { username: "trevin", password: "trevin", label: "Trevin Wisaksana", role: "Engineering — your files" },
];

export default function LoginPage() {
  const { ready, isAuthed, isAdmin, login } = useSession();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Once the session is hydrated and we're authenticated, leave the login screen.
  useEffect(() => {
    if (ready && isAuthed) {
      router.replace(isAdmin ? "/admin" : "/files");
    }
  }, [ready, isAuthed, isAdmin, router]);

  function attempt(u: string, p: string) {
    setSubmitting(true);
    setError(null);
    const result = login(u, p);
    if (!result.ok) {
      setError(result.error ?? "Unable to sign in.");
      setSubmitting(false);
    }
    // On success, the redirect effect above handles navigation.
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    attempt(username, password);
  }

  function handleChip(chip: DemoChip) {
    setUsername(chip.username);
    setPassword(chip.password);
    attempt(chip.username, chip.password);
  }

  // While hydrating the persisted session (or mid-redirect), show a quiet placeholder.
  if (!ready || isAuthed) {
    return (
      <div className="grid min-h-screen place-items-center bg-bg">
        <Spinner className="h-6 w-6 text-accent" />
      </div>
    );
  }

  return (
    <main
      className="relative grid min-h-screen place-items-center overflow-hidden bg-bg px-4 py-10"
      style={{
        backgroundImage:
          "radial-gradient(60rem 40rem at 50% -10%, var(--tw-gradient-stops)), radial-gradient(48rem 32rem at 110% 110%, var(--tw-gradient-stops))",
      }}
    >
      {/* Soft ambient accent wash behind the card */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-bg"
        style={{
          backgroundImage:
            "radial-gradient(42rem 28rem at 50% -8%, var(--accent-soft, rgba(8,145,178,0.16)), transparent 70%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 left-1/2 h-[26rem] w-[26rem] -translate-x-1/2 rounded-full bg-accent-soft opacity-60 blur-3xl"
      />

      <div className="relative z-10 w-full max-w-[420px] animate-fadeIn">
        <div className="card card-pad rounded-2xl !p-8 shadow-lg">
          {/* Brand mark */}
          <div className="flex flex-col items-center text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-white shadow-md">
              <ShieldCheck className="h-7 w-7" strokeWidth={2.2} />
            </div>
            <h1 className="mt-4 text-[1.35rem] font-semibold tracking-tight text-ink">
              GDPR Data Discovery
            </h1>
            <p className="mt-1.5 text-[0.85rem] leading-relaxed text-ink-muted">
              Find and resolve personal data across your corporate file sources.
            </p>
          </div>

          {/* Sign-in form */}
          <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="username" className="label-tiny">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoFocus
                className="input"
                placeholder="admin"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (error) setError(null);
                }}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="label-tiny">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="input"
                placeholder="••••••"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(null);
                }}
              />
            </div>

            {error && (
              <p className="text-[0.8rem] font-medium text-danger-text" role="alert">
                {error}
              </p>
            )}

            <Button
              type="submit"
              variant="primary"
              className="mt-1 w-full justify-center"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Spinner className="h-4 w-4" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>

          {/* Divider */}
          <div className="my-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-line-soft" />
            <span className="label-tiny">Demo accounts</span>
            <span className="h-px flex-1 bg-line-soft" />
          </div>

          {/* Demo account chips */}
          <div className="flex flex-col gap-2.5">
            {DEMO_CHIPS.map((chip) => (
              <button
                key={chip.username}
                type="button"
                onClick={() => handleChip(chip)}
                disabled={submitting}
                className="group flex w-full items-center gap-3 rounded-xl border border-line bg-surface-alt px-3.5 py-3 text-left transition hover:border-accent-line hover:bg-accent-soft disabled:opacity-60"
              >
                <span className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-surface text-accent-strong shadow-sm">
                  {chip.username === "admin" ? (
                    <ShieldCheck className="h-[18px] w-[18px]" />
                  ) : (
                    <ScanSearch className="h-[18px] w-[18px]" />
                  )}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[0.85rem] font-semibold text-ink">{chip.label}</span>
                  <span className="block text-[0.74rem] text-ink-muted">{chip.role}</span>
                </span>
                <code className="badge badge-mono flex-none">
                  {chip.username} / {chip.password}
                </code>
                <ArrowRight className="h-4 w-4 flex-none text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-accent-strong" />
              </button>
            ))}
          </div>
        </div>

        {/* Footer micro-text */}
        <div className="mt-5 flex flex-col items-center gap-1.5 text-center">
          <p className="text-[0.74rem] text-ink-faint">
            Prototype · TECHon hackathon · Bosch GDPR challenge
          </p>
          <p className="inline-flex items-center gap-1.5 text-[0.7rem] text-ink-faint">
            <Lock className="h-3 w-3" />
            Demo environment — no real authentication.
          </p>
        </div>
      </div>
    </main>
  );
}
