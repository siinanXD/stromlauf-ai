import { afterEach, describe, expect, it } from "vitest";

import { clearToken, getToken, setToken, tokenValid } from "./auth";

function fakeJwt(exp: number): string {
  const b64 = (s: string) => Buffer.from(s).toString("base64").replace(/=+$/, "");
  return `${b64('{"alg":"HS256"}')}.${b64(JSON.stringify({ sub: "u", ws: "w", exp }))}.sig`;
}

describe("auth token", () => {
  afterEach(() => clearToken());

  it("speichert und loescht das Token", () => {
    expect(getToken()).toBeNull();
    setToken("abc");
    expect(getToken()).toBe("abc");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("prueft den Ablauf aus dem JWT", () => {
    const now = 1_700_000_000_000;
    expect(tokenValid(fakeJwt(now / 1000 + 60), now)).toBe(true);
    expect(tokenValid(fakeJwt(now / 1000 - 60), now)).toBe(false);
    expect(tokenValid("kein.jwt", now)).toBe(false);
    expect(tokenValid(null, now)).toBe(false);
  });
});
