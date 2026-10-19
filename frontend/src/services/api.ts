import { request } from "./http";
import {
  accountSchema,
  healthSchema,
  loginSchema,
  pageSchema,
  paymentSchema,
  userSchema,
  type PaymentBody,
} from "../types/api";
const paged = (resource: string, cursor: string | null) =>
  `${resource}?limit=20${cursor ? "&cursor=" + encodeURIComponent(cursor) : ""}`;
export const api = {
  login: (email: string, password: string) =>
    request("/api/auth/login", loginSchema, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request("/api/auth/me", userSchema),
  accounts: (cursor: string | null = null) =>
    request(paged("/api/accounts", cursor), pageSchema(accountSchema)),
  account: (id: string) =>
    request("/api/accounts/" + encodeURIComponent(id), accountSchema),
  payments: (cursor: string | null = null) =>
    request(paged("/api/payments", cursor), pageSchema(paymentSchema)),
  payment: (id: string) =>
    request("/api/payments/" + encodeURIComponent(id), paymentSchema),
  transfer: (body: PaymentBody, key: string) =>
    request(
      "/api/payments",
      paymentSchema,
      {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify(body),
      },
      true,
    ),
  health: (service: "auth" | "payment") =>
    request("/status/" + service, healthSchema),
};
