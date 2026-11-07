import { describe, expect, it } from "vitest";

import { isNonPublicApiUrl, publicBuildApiUrl } from "./apiUrl";

describe("isNonPublicApiUrl", () => {
  it.each([
    "https://sinanspc.tail046f7f.ts.net:8443",
    "http://100.101.102.103:8010",
    "http://192.168.1.20:8010",
    "http://10.0.0.5",
    "http://172.20.1.1",
    "http://localhost:8010",
    "http://127.0.0.1:8010",
    "http://rechner.local",
    "http://[::1]:8010",
    "http://[fd7a:115c:a1e0::1]:8010",
    "http://[fe80::1]",
    "http://[::ffff:10.0.0.1]",
    "http://169.254.169.254",
    "kein url",
  ])("%s ist nicht oeffentlich", (url) => expect(isNonPublicApiUrl(url)).toBe(true));

  it.each(["https://api.example.com", "https://stromlauf-api.fly.dev/", "http://172.32.0.1", "http://100.128.0.1", "http://8.8.8.8:8010", "http://[2a01:4f8::1]:8010"])(
    "%s ist oeffentlich",
    (url) => expect(isNonPublicApiUrl(url)).toBe(false),
  );
});

describe("publicBuildApiUrl", () => {
  const tailnet = "https://sinanspc.tail046f7f.ts.net:8443";

  it("drops a Tailnet or unset address on Vercel so the bundle holds no address", () => {
    expect(publicBuildApiUrl(tailnet, true)).toBe("");
    expect(publicBuildApiUrl(undefined, true)).toBe("");
    expect(publicBuildApiUrl("http://localhost:8010", true)).toBe("");
  });

  it("keeps a public address on Vercel and every address elsewhere", () => {
    expect(publicBuildApiUrl("https://api.example.com", true)).toBe("https://api.example.com");
    expect(publicBuildApiUrl(tailnet, false)).toBe(tailnet);
    expect(publicBuildApiUrl(undefined, false)).toBeUndefined();
  });
});
