import type { NextConfig } from "next";

import { publicBuildApiUrl } from "./src/lib/apiUrl";

// Vercel baut mit einer Variablen aus dem Dashboard; eine Tailnet-Adresse darf nicht ins oeffentliche Bundle (SIN-1522)
if (process.env.VERCEL) {
  process.env.NEXT_PUBLIC_API_URL = publicBuildApiUrl(process.env.NEXT_PUBLIC_API_URL, true);
  if (process.env.NEXT_PUBLIC_API_URL === "") console.warn("NEXT_PUBLIC_API_URL: keine oeffentliche Adresse, der Build laeuft ohne Backend");
}

const nextConfig: NextConfig = {
  async redirects() {
    // Der Standortplan unter /werk ist entfernt; alte Lesezeichen landen in der Maschinenuebersicht
    return [{ source: "/werk", destination: "/werk/maschinen", permanent: false }];
  },
};

export default nextConfig;
