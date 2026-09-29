import { beforeEach, describe, expect, it } from "vitest";

import { lastAnswerMeta, recallConversation, rememberConversation } from "./chatMemory";

class FakeStorage {
  private data = new Map<string, string>();
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
}

describe("rememberConversation / recallConversation", () => {
  beforeEach(() => {
    (globalThis as { localStorage?: unknown }).localStorage = new FakeStorage();
  });

  it("remembers the conversation per machine and forgets it with null", () => {
    rememberConversation("m-1", "conv-1");
    rememberConversation("m-2", "conv-9");
    expect(recallConversation("m-1")).toBe("conv-1");
    expect(recallConversation("m-2")).toBe("conv-9");
    rememberConversation("m-1", null);
    expect(recallConversation("m-1")).toBeNull();
  });

  it("survives a missing or throwing storage", () => {
    (globalThis as { localStorage?: unknown }).localStorage = undefined;
    expect(() => rememberConversation("m-1", "conv-1")).not.toThrow();
    expect(recallConversation("m-1")).toBeNull();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => rememberConversation("m-1", "conv-1")).not.toThrow();
    expect(recallConversation("m-1")).toBeNull();
  });
});

describe("lastAnswerMeta", () => {
  const meta = { referenced_tags: ["-K1"], citations: [], evidence: [] };
  it("returns the meta of the last assistant message that has one", () => {
    const messages = [
      { role: "user" as const, content: "a", tool_calls: [], sources: [] },
      { role: "assistant" as const, content: "b", tool_calls: [], sources: [], meta },
      { role: "user" as const, content: "c", tool_calls: [], sources: [] },
      { role: "assistant" as const, content: "d", tool_calls: [], sources: [] },
    ];
    expect(lastAnswerMeta(messages)).toBe(meta);
    expect(lastAnswerMeta(messages.slice(0, 1))).toBeUndefined();
    expect(lastAnswerMeta([])).toBeUndefined();
  });
});
