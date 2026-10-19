import { describe, it, expect, vi } from "vitest";
import {
  createIntent,
  saveIntent,
  loadIntent,
  clearIntent,
  submitIntent,
} from "./intent";
import { api } from "../../services/api";
import { formSchema } from "./Payments";
const body = {
  source_account_id: "20000000-0000-4000-8000-000000000001",
  destination_account_id: "20000000-0000-4000-8000-000000000002",
  amount_minor: 100,
  currency: "EUR" as const,
};
describe("payment intentions", () => {
  it("creates a fresh key per new intention", () =>
    expect(createIntent(body).key).not.toBe(createIntent(body).key));
  it("restores the same body and key for this user and tab", () => {
    const intent = createIntent(body);
    saveIntent("alice", intent);
    expect(loadIntent("alice")).toEqual(intent);
    expect(loadIntent("bob")).toBeNull();
    clearIntent("alice");
    expect(loadIntent("alice")).toBeNull();
  });
  it("deduplicates simultaneous requests and preserves key on retry", async () => {
    const intent = createIntent(body);
    const transfer = vi
      .spyOn(api, "transfer")
      .mockRejectedValue(new Error("network"));
    const first = submitIntent(intent);
    const second = submitIntent(intent);
    expect(first).toBe(second);
    await expect(first).rejects.toThrow();
    await expect(submitIntent(intent)).rejects.toThrow();
    expect(transfer).toHaveBeenCalledTimes(2);
    expect(transfer.mock.calls.map((c) => c[1])).toEqual([
      intent.key,
      intent.key,
    ]);
  });
  it("rejects self transfers", () =>
    expect(
      formSchema.safeParse({
        source: body.source_account_id,
        destination: body.source_account_id,
        amount: "1",
        currency: "EUR",
      }).success,
    ).toBe(false));
  it("rejects unsupported currency", () =>
    expect(
      formSchema.safeParse({
        source: body.source_account_id,
        destination: body.destination_account_id,
        amount: "1",
        currency: "USD",
      }).success,
    ).toBe(false));
});
