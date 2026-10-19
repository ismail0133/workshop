import type { z } from "zod";
let token: string | null = null;
let onUnauthorized: () => void = () => {};
export function setSessionToken(value: string | null) {
  token = value;
}
export function onSessionExpired(callback: () => void) {
  onUnauthorized = callback;
  return () => {
    onUnauthorized = () => {};
  };
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: unknown = null,
  ) {
    super(message);
  }
}
const base = import.meta.env.VITE_API_BASE_URL || "";
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
  allowRejected = false,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  const currentToken = token;
  try {
    const response = await fetch(base + path, {
      ...options,
      signal: controller.signal,
      credentials: "omit",
      headers: {
        "Content-Type": "application/json",
        ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
        ...options.headers,
      },
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.status === 401 && currentToken && token === currentToken)
      onUnauthorized();
    if (
      !response.ok &&
      !(
        allowRejected &&
        response.status === 409 &&
        schema.safeParse(body).success
      )
    ) {
      const messages: Record<number, string> = {
        401: "Identifiants incorrects ou session expirée.",
        403: "Votre rôle ne permet pas cette opération.",
        404: "Compte ou transaction introuvable ou non autorisé.",
        409: "Cette clé est déjà liée à une autre opération.",
        422: "Les informations envoyées sont invalides.",
        429: "Trop de tentatives. Réessayez dans une minute.",
        503: "Service indisponible. Réessayez avec la même opération.",
      };
      throw new ApiError(
        response.status,
        messages[response.status] ||
          "Le service ne peut pas traiter la demande.",
        body,
      );
    }
    const parsed = schema.safeParse(body);
    if (!parsed.success)
      throw new ApiError(
        502,
        "Réponse du service invalide. Réessayez sans modifier l’opération.",
      );
    return parsed.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      "Connexion interrompue ou délai dépassé. Le résultat est inconnu : réessayez la même opération.",
    );
  } finally {
    clearTimeout(timer);
  }
}
