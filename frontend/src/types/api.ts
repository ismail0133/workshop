import { z } from "zod";
export const userSchema = z.object({
  id: z.uuid(),
  email: z.string(),
  role: z.enum(["USER", "OPERATOR", "ADMIN", "VALIDATOR"]),
});
export type User = z.infer<typeof userSchema>;
export const loginSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer").default("bearer"),
  expires_in: z.literal(900).default(900),
  user: userSchema,
});
export const accountSchema = z.object({
  id: z.uuid(),
  owner_user_id: z.uuid(),
  label: z.string(),
  balance_minor: z.number().int().min(0).max(1e12),
  currency: z.literal("EUR"),
  status: z.enum(["ACTIVE", "FROZEN"]),
  is_synthetic: z.boolean(),
  created_at: z.iso.datetime({ offset: true }),
  updated_at: z.iso.datetime({ offset: true }),
});
export type Account = z.infer<typeof accountSchema>;
export const paymentSchema = z.object({
  id: z.uuid(),
  actor_user_id: z.uuid(),
  source_account_id: z.uuid(),
  destination_account_id: z.uuid(),
  amount_minor: z.number().int().positive(),
  currency: z.literal("EUR"),
  status: z.enum(["SUCCESS", "REJECTED"]),
  failure_code: z
    .enum(["INSUFFICIENT_FUNDS", "ACCOUNT_FROZEN", "BALANCE_LIMIT"])
    .nullable(),
  created_at: z.iso.datetime({ offset: true }),
});
export type Payment = z.infer<typeof paymentSchema>;
export const pageSchema = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), next_cursor: z.string().nullable() });
export const healthSchema = z.object({
  status: z.enum(["ok", "degraded", "unavailable"]),
  service: z.string(),
  checked_at: z.iso.datetime({ offset: true }),
});
export type PaymentBody = {
  source_account_id: string;
  destination_account_id: string;
  amount_minor: number;
  currency: "EUR";
};
