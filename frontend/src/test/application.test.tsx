import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";
import { AuthProvider } from "../features/auth/AuthProvider";
import { ToastProvider } from "../components/ui";
const uid = "10000000-0000-4000-8000-000000000001";
const aid = "20000000-0000-4000-8000-000000000001";
const bid = "20000000-0000-4000-8000-000000000002";
const tid = "30000000-0000-4000-8000-000000000001";
const when = "2026-10-19T10:00:00Z";
const payment = {
  id: tid,
  actor_user_id: uid,
  source_account_id: aid,
  destination_account_id: bid,
  amount_minor: 125,
  currency: "EUR",
  status: "SUCCESS",
  failure_code: null,
  created_at: when,
};
function setup(path = "/login", role = "USER") {
  const calls: { url: string; options: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit = {}) => {
      calls.push({ url, options });
      let body: unknown = {};
      if (url === "/api/auth/login")
        body = {
          access_token: "mock-token",
          expires_in: 900,
          token_type: "bearer",
          user: { id: uid, email: "alice@resilience.test", role },
        };
      else if (url === "/api/auth/me")
        body = { id: uid, email: "alice@resilience.test", role };
      else if (url.startsWith("/status/"))
        body = { status: "ok", service: "mock", checked_at: when };
      else if (url.startsWith("/api/accounts?"))
        body = {
          items: [
            {
              id: aid,
              owner_user_id: uid,
              label: "Compte A",
              balance_minor: 80000,
              currency: "EUR",
              status: "ACTIVE",
              is_synthetic: false,
              created_at: when,
              updated_at: when,
            },
          ],
          next_cursor: null,
        };
      else if (url.startsWith("/api/payments?"))
        body = { items: [payment], next_cursor: null };
      else if (url === "/api/payments" && options.method === "POST")
        body = payment;
      else if (url.startsWith("/api/payments/")) body = payment;
      return new Response(JSON.stringify(body), {
        status:
          options.method === "POST" && url === "/api/payments" ? 201 : 200,
      });
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return calls;
}
async function login() {
  const u = userEvent.setup();
  await u.type(
    screen.getByLabelText("Adresse e-mail"),
    "alice@resilience.test",
  );
  await u.type(screen.getByLabelText("Mot de passe"), "test-password");
  await u.click(screen.getByRole("button", { name: "Se connecter" }));
  await screen.findByRole("heading", { name: "Votre centre de contrôle." });
  return u;
}
describe("application with explicit HTTP mocks", () => {
  it("protects deep links without a session", () => {
    setup("/accounts");
    expect(
      screen.getByRole("button", { name: "Se connecter" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Compte A")).not.toBeInTheDocument();
  });
  it("validates login fields", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(
      await screen.findByText("Adresse e-mail invalide."),
    ).toBeInTheDocument();
  });
  it("logs in, verifies current user, navigates and logs out", async () => {
    const calls = setup();
    const u = await login();
    expect(calls.some((c) => c.url === "/api/auth/me")).toBe(true);
    await u.click(screen.getByRole("link", { name: "Accounts" }));
    expect(await screen.findByText("Compte A")).toBeInTheDocument();
    await u.click(screen.getByRole("link", { name: "Transactions" }));
    expect(
      await screen.findByRole("heading", {
        name: "Historique des transactions",
      }),
    ).toBeInTheDocument();
    await u.click(screen.getByText("alice", { selector: ".user-text" }));
    await u.click(screen.getByRole("button", { name: "Se déconnecter" }));
    expect(
      await screen.findByRole("button", { name: "Se connecter" }),
    ).toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
  });
  it("performs confirmed payment with an idempotency header", async () => {
    const calls = setup();
    const u = await login();
    await u.click(screen.getByRole("link", { name: "Payments" }));
    await u.selectOptions(await screen.findByLabelText("Compte source"), aid);
    await u.type(screen.getByLabelText("Compte destinataire"), bid);
    await u.type(screen.getByLabelText("Montant"), "1,25");
    await u.click(screen.getByRole("button", { name: "Vérifier le virement" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await u.click(
      screen.getByRole("button", { name: "Confirmer le paiement" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Virement enregistré" }),
    ).toBeInTheDocument();
    const posts = calls.filter(
      (c) => c.url === "/api/payments" && c.options.method === "POST",
    );
    expect(posts).toHaveLength(1);
    expect(
      (posts[0].options.headers as Record<string, string>)["Idempotency-Key"],
    ).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(posts[0].options.body as string).amount_minor).toBe(125);
  });
  it("shows future modules without fabricated data", async () => {
    setup();
    const u = await login();
    for (const name of [
      "Security Center",
      "AI Detection",
      "Autonomous Recovery",
      "AI Assistant",
    ]) {
      await u.click(screen.getByRole("link", { name }));
      expect(screen.getAllByText("NOT CONFIGURED").length).toBeGreaterThan(0);
    }
    expect(
      screen.getByRole("button", { name: "Envoyer la question" }),
    ).toBeDisabled();
  });
  it("prevents operator banking requests", async () => {
    const calls = setup("/login", "OPERATOR");
    const u = await login();
    await u.click(screen.getByRole("link", { name: /Accounts/ }));
    expect(
      await screen.findByText("Accès bancaire non autorisé"),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        calls.filter((c) => c.url.startsWith("/api/accounts")),
      ).toHaveLength(0),
    );
  });
  it("shows server errors on login", async () => {
    setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 401 })),
    );
    const u = userEvent.setup();
    await u.type(
      screen.getByLabelText("Adresse e-mail"),
      "alice@resilience.test",
    );
    await u.type(screen.getByLabelText("Mot de passe"), "wrong");
    await u.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Identifiants incorrects",
    );
  });
  it("expires a suspended session when the tab regains focus", async () => {
    setup();
    await login();
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 901000);
    fireEvent(window, new Event("focus"));
    expect(
      await screen.findByRole("button", { name: "Se connecter" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("session a expiré");
  });
  it("loads the next opaque cursor without claiming a total", async () => {
    setup();
    const original = globalThis.fetch;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, options?: RequestInit) => {
        if (url.startsWith("/api/payments?")) {
          return new Response(
            JSON.stringify(
              url.includes("cursor=")
                ? {
                    items: [
                      {
                        ...payment,
                        id: "30000000-0000-4000-8000-000000000002",
                      },
                    ],
                    next_cursor: null,
                  }
                : { items: [payment], next_cursor: "opaque-test-cursor" },
            ),
          );
        }
        return original(url, options);
      }),
    );
    const u = await login();
    await u.click(
      screen.getByRole("link", { name: "Transactions" }),
    );
    expect(await screen.findByText(/Historique partiel/)).toBeInTheDocument();
    await u.click(
      screen.getByRole("button", { name: "Charger la page suivante" }),
    );
    expect(await screen.findByText("2 CHARGÉES")).toBeInTheDocument();
    expect(
      screen.getByText("Fin des résultats récupérés."),
    ).toBeInTheDocument();
  });
});
