"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SteckbriefKarte } from "@/components/SteckbriefKarte";
import { api, type SourceProfile } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Steckbrief einer Wissensquelle: welche Dokumente da sind, wie sie zusammenpassen, was fehlt. Ohne KI-Kosten. */
export default function SourceProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<SourceProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSourceProfile(id)
      .then(setProfile)
      .catch((err) => setError((err as Error).message));
  }, [id]);

  const name = profile?.source_name ?? "…";
  return (
    <AppShell breadcrumb={[{ label: "Chat", href: "/" }, { label: "Wissensquelle" }, { label: name }]}>
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-2">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Steckbrief {name}</h1>
          {profile && (
            <span className="text-sm text-muted-foreground">
              {profile.summary.devices} Betriebsmittel · {profile.summary.terminals} Klemmen · {profile.summary.plc_addresses} SPS-Adressen ·{" "}
              <span className={cn(profile.summary.gaps > 0 && "font-medium text-danger")}>
                {profile.summary.gaps === 0 ? "keine Lücken" : `${profile.summary.gaps} Lücken`}
              </span>
              {profile.sheets.length > 0 && ` · Plan mit ${profile.sheets.length} Blättern`}
            </span>
          )}
        </div>
        {error && <p className="border-b border-border px-4 py-1.5 text-xs text-danger">{error}</p>}

        {profile && (
          <div className="min-h-0 flex-1 overflow-y-auto p-4 md:px-6">
            <SteckbriefKarte profile={profile} />
          </div>
        )}
      </div>
    </AppShell>
  );
}
