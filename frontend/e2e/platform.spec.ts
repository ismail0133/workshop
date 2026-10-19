import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "../..");
const evidence = resolve(root, "docs/evidence/phase2");
const source = "20000000-0000-4000-8000-000000000003";
const destination = "20000000-0000-4000-8000-000000000004";
function sql(query: string) {
  return execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "resilience_bootstrap",
      "-d",
      "resilience",
      "-tAc",
      query,
    ],
    { cwd: root, encoding: "utf8" },
  ).trim();
}
async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Adresse e-mail").fill("validator@resilience.test");
  await page
    .getByLabel("Mot de passe")
    .fill(
      readFileSync(
        resolve(root, "infrastructure/secrets/runtime/demo_validator_password"),
        "utf8",
      ).trim(),
    );
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(
    page.getByRole("heading", { name: "Votre centre de contrôle." }),
  ).toBeVisible();
}
test("real React payment: lost response, same-key retry, history and PostgreSQL consistency", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/accounts");
  await expect(
    page.getByRole("button", { name: "Se connecter" }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(evidence, "login-desktop.png"),
    fullPage: true,
  });
  await login(page);
  const before = JSON.parse(
    sql(
      `SELECT json_object_agg(id,balance_minor) FROM bank.accounts WHERE id IN ('${source}','${destination}')`,
    ),
  );
  const historicalBefore = sql(
    "SELECT json_object_agg(label,balance_minor) FROM bank.accounts WHERE label IN ('Compte A','Compte B')",
  );
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Compte V1", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Payments", exact: true }).click();
  await page.getByLabel("Compte source").selectOption(source);
  await page.getByLabel("Compte destinataire").fill(destination);
  await page.getByLabel("Montant", { exact: true }).fill("1,25");
  await page.getByRole("button", { name: "Vérifier le virement" }).click();
  let key = "";
  let firstId = "";
  let firstStatus = 0;
  let replayStatus = 0;
  let posts = 0;
  await page.route("**/api/payments", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    posts++;
    const incoming = route.request().headers()["idempotency-key"];
    if (!key) key = incoming;
    else expect(incoming).toBe(key);
    const response = await route.fetch();
    if (posts === 1) {
      firstStatus = response.status();
      firstId = (await response.json()).id;
      await route.abort("failed");
    } else {
      replayStatus = response.status();
      await route.fulfill({ response });
    }
  });
  await page.getByRole("button", { name: "Confirmer le paiement" }).dblclick();
  await expect(page.getByRole("alert")).toContainText("résultat est inconnu");
  // Navigate away and return: the same intent survives component unmount.
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  await page.getByRole("link", { name: "Payments", exact: true }).click();
  await page
    .getByRole("button", { name: "Reprendre la même opération" })
    .click();
  await page.getByRole("button", { name: "Confirmer le paiement" }).click();
  await expect(
    page.getByRole("heading", { name: "Virement enregistré", exact: true }),
  ).toBeVisible();
  expect(posts).toBe(2);
  expect(firstStatus).toBe(201);
  expect(replayStatus).toBe(200);
  await expect(page.getByText(firstId, { exact: true })).toBeVisible();
  await page.screenshot({
    path: resolve(evidence, "payment-success.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Consulter la transaction" }).click();
  await expect(page.getByText(firstId, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  const formatted = new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format((before[source] - 125) / 100);
  await expect(page.getByText(formatted, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Transactions", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Détails " + firstId }),
  ).toBeVisible();
  const after = JSON.parse(
    sql(
      `SELECT json_object_agg(id,balance_minor) FROM bank.accounts WHERE id IN ('${source}','${destination}')`,
    ),
  );
  expect(after[source]).toBe(before[source] - 125);
  expect(after[destination]).toBe(before[destination] + 125);
  expect(key).toMatch(/^[0-9a-f-]{36}$/);
  const count = Number(
    sql(
      `SELECT count(*) FROM bank.transactions WHERE idempotency_key='${key}' AND status='SUCCESS'`,
    ),
  );
  expect(count).toBe(1);
  expect(
    sql(
      "SELECT json_object_agg(label,balance_minor) FROM bank.accounts WHERE label IN ('Compte A','Compte B')",
    ),
  ).toBe(historicalBefore);
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Votre centre de contrôle." }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(evidence, "overview-desktop.png"),
    fullPage: true,
  });
  for (const name of [
    "Infrastructure",
    "Security Center",
    "AI Detection",
    "Autonomous Recovery",
    "AI Assistant",
  ]) {
    await page.getByRole("link", { name, exact: true }).click();
    await expect(page.getByText("NOT CONFIGURED").first()).toBeVisible();
  }
  await expect(
    page.getByRole("button", { name: "Envoyer la question" }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Ouvrir la navigation" }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.locator(".sidebar")).not.toHaveClass(/open/);
  await expect(
    page.getByRole("heading", { name: "Votre centre de contrôle." }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(evidence, "overview-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(
    await page.evaluate(() =>
      Object.keys(sessionStorage).some((k) => /token/i.test(k)),
    ),
  ).toBe(false);
  await page.locator(".user-menu summary").click();
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await expect(
    page.getByRole("button", { name: "Se connecter" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  writeFileSync(
    resolve(evidence, "e2e-payment.json"),
    JSON.stringify(
      {
        before_minor: before,
        after_minor: after,
        amount_minor: 125,
        transaction_id: firstId,
        idempotency_key: key,
        first_http: firstStatus,
        replay_http: replayStatus,
        post_requests: posts,
        database_rows: count,
        historical_accounts_unchanged: true,
        browser_errors: errors,
      },
      null,
      2,
    ) + "\n",
  );
});
test("real session reload requires login", async ({ page }) => {
  await login(page);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Se connecter" }),
  ).toBeVisible();
});
