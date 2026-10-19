import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ShieldCheck,
  ArrowLeftRight,
  CheckCircle2,
} from "lucide-react";
import { useAccounts } from "../../hooks/useData";
import { useAuth } from "../auth/AuthProvider";
import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  Input,
  Modal,
  PageTitle,
  Skeleton,
  useToast,
} from "../../components/ui";
import { money, toMinor } from "../../utils/money";
import type { Payment } from "../../types/api";
import {
  clearIntent,
  createIntent,
  loadIntent,
  saveIntent,
  submitIntent,
  type Intent,
} from "./intent";
export const formSchema = z
  .object({
    source: z.uuid("Choisissez un compte source."),
    destination: z.uuid("Saisissez un UUID de compte valide."),
    amount: z.string().refine((v) => {
      try {
        toMinor(v);
        return true;
      } catch {
        return false;
      }
    }, "Montant positif requis, avec au plus deux décimales."),
    currency: z.literal("EUR"),
  })
  .refine((v) => v.source !== v.destination, {
    path: ["destination"],
    message: "Les deux comptes doivent être différents.",
  });
export function Payments() {
  const { user } = useAuth();
  const query = useAccounts();
  const client = useQueryClient();
  const toast = useToast();
  const [intent, setIntent] = useState<Intent | null>(() =>
    loadIntent(user!.id),
  );
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const flight = useRef(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Payment | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { currency: "EUR" },
  });
  const accounts = query.data?.pages.flatMap((p) => p.items) || [];
  async function execute() {
    if (!intent || flight.current) return;
    flight.current = true;
    setBusy(true);
    setError("");
    try {
      const value = await submitIntent(intent);
      setResult(value);
      clearIntent(user!.id);
      setIntent(null);
      setConfirm(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["accounts"] }),
        client.invalidateQueries({ queryKey: ["payments"] }),
        client.invalidateQueries({ queryKey: ["account"] }),
      ]);
      toast(
        value.status === "SUCCESS"
          ? "Virement enregistré. Soldes actualisés."
          : "Paiement rejeté : aucun mouvement de fonds.",
      );
    } catch (e) {
      setError((e as Error).message);
      setConfirm(false);
    } finally {
      flight.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="BANKING / PAYMENTS"
        title="Un virement, en toute clarté."
        description="Transférez des fonds fictifs avec confirmation et protection contre les doublons."
      />
      <div className="payment-grid">
        <Card className="payment-form">
          <div className="section-heading">
            <h2>Nouveau virement</h2>
            <Badge tone="cyan">EUR TRANSFER</Badge>
          </div>
          {result ? (
            <div className="payment-result">
              <CheckCircle2 size={42} />
              <Badge tone={result.status === "SUCCESS" ? "good" : "bad"}>
                {result.status}
              </Badge>
              <h2>
                {result.status === "SUCCESS"
                  ? "Virement enregistré"
                  : "Virement rejeté"}
              </h2>
              <strong>{money(result.amount_minor)}</strong>
              {result.failure_code && (
                <Alert>
                  {
                    {
                      INSUFFICIENT_FUNDS: "Solde insuffisant.",
                      ACCOUNT_FROZEN: "Un compte est gelé.",
                      BALANCE_LIMIT: "Le plafond de solde serait dépassé.",
                    }[result.failure_code]
                  }
                </Alert>
              )}
              <p className="mono">{result.id}</p>
              <Link className="text-link" to={"/transactions/" + result.id}>
                Consulter la transaction <ArrowRight size={16} />
              </Link>
              <Button
                onClick={() => {
                  setResult(null);
                  reset();
                }}
              >
                Nouveau virement
              </Button>
            </div>
          ) : intent ? (
            <div className="intent-summary">
              <Badge tone="cyan">OPÉRATION CONSERVÉE</Badge>
              <h3>{money(intent.body.amount_minor)}</h3>
              <dl className="details">
                <dt>Compte source</dt>
                <dd>{intent.body.source_account_id}</dd>
                <dt>Compte destinataire</dt>
                <dd>{intent.body.destination_account_id}</dd>
                <dt>Clé d’idempotence</dt>
                <dd>{intent.key}</dd>
              </dl>
              <p>
                Le résultat peut être inconnu après une interruption. Reprenez
                cette même opération : sa clé est conservée, même après un
                rechargement de cet onglet.
              </p>
              {error && <Alert>{error}</Alert>}
              <Button onClick={() => setConfirm(true)} disabled={busy}>
                {busy ? "Envoi en cours…" : "Reprendre la même opération"}
              </Button>
              <p className="fine-print">
                Vérifiez l’historique avant d’abandonner une opération dont le
                résultat est inconnu.
              </p>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      "Une opération peut déjà avoir été enregistrée. Avez-vous vérifié son résultat dans l’historique ?",
                    )
                  ) {
                    clearIntent(user!.id);
                    setIntent(null);
                    setError("");
                  }
                }}
              >
                Abandonner après vérification
              </Button>
            </div>
          ) : query.isPending ? (
            <Skeleton />
          ) : query.isError ? (
            <ErrorState error={query.error} retry={() => query.refetch()} />
          ) : (
            <form
              noValidate
              onSubmit={handleSubmit((values) => {
                setError("");
                const next = createIntent({
                  source_account_id: values.source,
                  destination_account_id: values.destination,
                  amount_minor: toMinor(values.amount),
                  currency: "EUR",
                });
                try {
                  saveIntent(user!.id, next);
                  setIntent(next);
                  setConfirm(true);
                } catch {
                  setError(
                    "Le stockage de cet onglet est indisponible. Activez-le pour conserver la clé d’idempotence avant tout envoi.",
                  );
                }
              })}
            >
              <label htmlFor="source">Compte source</label>
              <select id="source" {...register("source")}>
                <option value="">Sélectionner un compte</option>
                {accounts.map((a) => (
                  <option
                    key={a.id}
                    value={a.id}
                    disabled={a.status !== "ACTIVE"}
                  >
                    {a.label} — {money(a.balance_minor)}
                  </option>
                ))}
              </select>
              {errors.source && (
                <small className="field-error">{errors.source.message}</small>
              )}
              {query.hasNextPage && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => query.fetchNextPage()}
                  disabled={query.isFetchingNextPage}
                >
                  Charger d’autres comptes
                </Button>
              )}
              <label htmlFor="destination">Compte destinataire</label>
              <Input
                id="destination"
                placeholder="UUID du compte destinataire"
                {...register("destination")}
              />
              <small>
                Demandez l’identifiant au destinataire. Aucun annuaire de
                comptes tiers n’est exposé.
              </small>
              {errors.destination && (
                <small className="field-error">
                  {errors.destination.message}
                </small>
              )}
              <div className="form-row">
                <div>
                  <label htmlFor="amount">Montant</label>
                  <Input
                    id="amount"
                    inputMode="decimal"
                    placeholder="0,00"
                    {...register("amount")}
                  />
                </div>
                <div>
                  <label htmlFor="currency">Devise</label>
                  <select id="currency" {...register("currency")}>
                    <option value="EUR">EUR — Euro</option>
                  </select>
                </div>
              </div>
              {errors.amount && (
                <small className="field-error">{errors.amount.message}</small>
              )}
              {error && <Alert>{error}</Alert>}
              <div className="form-rule" />
              <Button
                type="submit"
                disabled={!accounts.some((a) => a.status === "ACTIVE")}
              >
                Vérifier le virement <ArrowRight size={17} />
              </Button>
            </form>
          )}
        </Card>
        <div>
          <Card className="payment-help">
            <span className="account-symbol">
              <ShieldCheck size={25} />
            </span>
            <h2>
              Une intention.
              <br />
              Une seule transaction.
            </h2>
            <p>
              Chaque virement dispose d’une clé unique. Une nouvelle tentative
              conserve cette clé pour éviter tout double débit.
            </p>
            <div className="help-step">
              <span>01</span>
              <div>
                <h3>Préparez</h3>
                <p>Choisissez les comptes et le montant.</p>
              </div>
            </div>
            <div className="help-step">
              <span>02</span>
              <div>
                <h3>Confirmez</h3>
                <p>Vérifiez les informations avant envoi.</p>
              </div>
            </div>
            <div className="help-step">
              <span>03</span>
              <div>
                <h3>Suivez</h3>
                <p>Retrouvez le résultat dans l’historique.</p>
              </div>
            </div>
          </Card>
          <p className="fine-print payment-disclaimer">
            <ArrowLeftRight size={16} />
            Transferts fictifs uniquement. Aucun paiement réel.
          </p>
        </div>
      </div>
      {confirm && intent && (
        <Modal
          title="Confirmer le virement"
          onClose={() => setConfirm(false)}
          busy={busy}
        >
          <p>Vérifiez ces informations avant de confirmer.</p>
          <h3 className="confirm-amount">{money(intent.body.amount_minor)}</h3>
          <dl className="details">
            <dt>Depuis</dt>
            <dd>{intent.body.source_account_id}</dd>
            <dt>Vers</dt>
            <dd>{intent.body.destination_account_id}</dd>
          </dl>
          <div className="modal-actions">
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Retour
            </Button>
            <Button disabled={busy} onClick={execute}>
              {busy ? "Envoi en cours…" : "Confirmer le paiement"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
