import { afterEach, describe, it, expect, vi } from "vitest";
import { z } from "zod";
import { request, setSessionToken, onSessionExpired } from "./http";
afterEach(() => {
  setSessionToken(null);
  vi.useRealTimers();
});
describe("HTTP boundary", () => {
  it("adds bearer only in memory and validates payload", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ value: 3 })));
    vi.stubGlobal("fetch", fetch);
    setSessionToken("test-only-token");
    expect(await request("/api/test", z.object({ value: z.number() }))).toEqual(
      { value: 3 },
    );
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe(
      "Bearer test-only-token",
    );
    expect(window.localStorage.length).toBe(0);
  });
  it("expires authenticated sessions on 401", async () => {
    const expired = vi.fn();
    onSessionExpired(expired);
    setSessionToken("test-only");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 401 })),
    );
    await expect(request("/api/test", z.object({}))).rejects.toMatchObject({
      status: 401,
    });
    expect(expired).toHaveBeenCalledOnce();
  });
  it("rejects invalid successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    await expect(
      request("/api/test", z.object({ id: z.uuid() })),
    ).rejects.toMatchObject({ status: 502 });
  });
  it("reports network uncertainty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError()));
    await expect(request("/api/test", z.object({}))).rejects.toMatchObject({
      status: 0,
    });
  });
  it("aborts after 12 seconds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, options) =>
          new Promise((_resolve, reject) =>
            options.signal.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            ),
          ),
      ),
    );
    const checked = expect(
      request("/api/test", z.object({})),
    ).rejects.toMatchObject({ status: 0 });
    await vi.advanceTimersByTimeAsync(12000);
    await checked;
  });
});
