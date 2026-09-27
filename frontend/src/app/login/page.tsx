"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { auth } from "@/lib/api";

/** Anmeldung per Magic-Link: E-Mail eingeben, Link kommt per Mail (oder im Dev-Modus direkt hier). */
export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await auth.magicLink(email.trim());
      setSent(true);
      setDevLink(result.dev_link);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-background p-6">
      <div className="w-full max-w-sm border border-line bg-card p-6">
        <div className="mb-5 flex items-center gap-3">
          <span className="grid size-9 place-items-center bg-primary font-mono text-lg font-semibold text-primary-foreground">S</span>
          <div>
            <h1 className="text-base font-semibold">Stromlauf AI</h1>
            <p className="text-xs text-muted-foreground">Anmeldung per Link, kein Passwort</p>
          </div>
        </div>
        {sent ? (
          <div className="space-y-3 text-sm">
            <p>
              {devLink ? "Dein Anmeldelink (Entwicklungsmodus):" : `Link an ${email} gesendet. Er ist 15 Minuten gültig.`}
            </p>
            {devLink && (
              <a href={devLink} className="block break-all font-mono text-xs text-primary underline">
                {devLink}
              </a>
            )}
            <Button variant="outline" type="button" onClick={() => setSent(false)}>
              Andere Adresse
            </Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">E-Mail</span>
              <Input
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@firma.de"
              />
            </label>
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" disabled={busy || !email.trim()} className="w-full">
              {busy ? "Sende …" : "Anmeldelink senden"}
            </Button>
          </form>
        )}
      </div>
    </main>
  );
}
