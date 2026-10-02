import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    // Der Standortplan unter /werk ist entfernt; alte Lesezeichen landen in der Maschinenuebersicht
    return [{ source: "/werk", destination: "/werk/maschinen", permanent: false }];
  },
};

export default nextConfig;
