export function toMinor(value: string): number {
  if (!/^(?:0|[1-9]\d{0,10})(?:[.,]\d{1,2})?$/.test(value.trim()))
    throw new Error(
      "Saisissez un montant positif, avec au plus deux décimales.",
    );
  const [whole, fraction = ""] = value.trim().replace(",", ".").split(".");
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(result) || result < 1 || result > 1e12)
    throw new Error(
      "Le montant doit être compris entre 0,01 € et 10 milliards d’euros.",
    );
  return result;
}
export const money = (minor: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(
    minor / 100,
  );
export const date = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
export const shortId = (value: string) =>
  value.slice(0, 8) + "…" + value.slice(-4);
