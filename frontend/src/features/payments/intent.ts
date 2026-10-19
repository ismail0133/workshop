import { z } from "zod";
import { api } from "../../services/api";
import type { PaymentBody, Payment } from "../../types/api";
const schema = z.object({
  key: z.uuid(),
  body: z.object({
    source_account_id: z.uuid(),
    destination_account_id: z.uuid(),
    amount_minor: z.number().int().positive().max(1e12),
    currency: z.literal("EUR"),
  }),
});
export type Intent = z.infer<typeof schema>;
const storageKey = (user: string) => "ra.payment-intent." + user;
export function loadIntent(user: string): Intent | null {
  try {
    return schema.parse(
      JSON.parse(sessionStorage.getItem(storageKey(user)) || "null"),
    );
  } catch {
    return null;
  }
}
export function saveIntent(user: string, intent: Intent) {
  sessionStorage.setItem(storageKey(user), JSON.stringify(intent));
}
export function clearIntent(user: string) {
  sessionStorage.removeItem(storageKey(user));
}
export const createIntent = (body: PaymentBody): Intent => ({
  key: crypto.randomUUID(),
  body,
});
const flights = new Map<string, Promise<Payment>>();
export function submitIntent(intent: Intent) {
  const existing = flights.get(intent.key);
  if (existing) return existing;
  const promise = api
    .transfer(intent.body, intent.key)
    .finally(() => flights.delete(intent.key));
  flights.set(intent.key, promise);
  return promise;
}
