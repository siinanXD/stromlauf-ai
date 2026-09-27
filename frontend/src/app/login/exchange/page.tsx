"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { auth } from "@/lib/api";
import { setToken } from "@/lib/auth";

function Exchange() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token");
  const [exchangeError, setExchangeError] = useState<string | null>(null);
  const error = token ? exchangeError : "Kein Token im Link.";

  useEffect(() => {
    if (!token) return;
    auth
      .exchange(token)
      .then((result) => {
        setToken(result.token);
        router.replace("/werk/maschinen");
      })
      .catch((err: Error) => setExchangeError(err.message));
  }, [token, router]);

  return (
    <main className="flex min-h-full items-center justify-center p-6 text-sm">
      {error ? (
        <div className="space-y-2 text-center">
          <p className="text-danger">{error}</p>
          <a href="/login" className="text-primary underline">
            Neuen Link anfordern
          </a>
        </div>
      ) : (
        <p className="text-muted-foreground">Anmeldung läuft …</p>
      )}
    </main>
  );
}

export default function ExchangePage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-muted-foreground">Anmeldung läuft …</p>}>
      <Exchange />
    </Suspense>
  );
}
