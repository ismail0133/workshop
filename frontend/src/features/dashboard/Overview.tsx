import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  CreditCard,
  Layers3,
  Wallet,
} from "lucide-react";
import { useAccounts, usePayments, useHealth } from "../../hooks/useData";
import { canBank, useAuth } from "../auth/AuthProvider";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  PageTitle,
  Skeleton,
} from "../../components/ui";
import { money } from "../../utils/money";
import { ActivityChart } from "../../components/charts/ActivityChart";
import { TransactionTable } from "../transactions/TransactionTable";
export function Overview() {
  const { user } = useAuth();
  const accounts = useAccounts();
  const payments = usePayments();
  const health = useHealth("payment");
  const rows = payments.data?.pages.flatMap((p) => p.items) || [];
  const list = accounts.data?.pages.flatMap((p) => p.items) || [];
  const bank = canBank(user);
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE / OVERVIEW"
        title="Votre centre de contrôle."
        description="Une vision claire de vos opérations et de votre environnement."
        action={
          bank ? (
            <Link className="button primary" to="/payments">
              Nouveau virement <ArrowUpRight size={17} />
            </Link>
          ) : (
            <Badge>{user?.role}</Badge>
          )
        }
      />
      <div className="context-strip">
        <span>
          <span className="dot" />
          DONNÉES DU LABORATOIRE
        </span>
        <p>Soldes fictifs · API connectées · Accès limité à votre rôle</p>
        <Badge tone="cyan">PHASE 02</Badge>
      </div>
      {bank ? (
        <>
          {accounts.isError && (
            <ErrorState
              error={accounts.error}
              retry={() => accounts.refetch()}
            />
          )}
          <div className="kpi-grid">
            {[
              {
                label: "Solde des comptes chargés",
                value:
                  accounts.isPending || accounts.isError
                    ? "—"
                    : money(list.reduce((s, a) => s + a.balance_minor, 0)),
                icon: Wallet,
                note: accounts.hasNextPage
                  ? "Vue partielle · autres comptes disponibles"
                  : "Comptes accessibles récupérés",
              },
              {
                label: "Comptes accessibles",
                value:
                  accounts.isPending || accounts.isError
                    ? "—"
                    : String(list.length),
                icon: CreditCard,
                note: accounts.hasNextPage
                  ? "Nombre chargé, non exhaustif"
                  : "Comptes récupérés",
              },
              {
                label: "Transactions chargées",
                value:
                  payments.isPending || payments.isError
                    ? "—"
                    : String(rows.length),
                icon: Layers3,
                note: payments.hasNextPage
                  ? "Historique partiel · 20 par page"
                  : "Historique récupéré",
              },
              {
                label: "Paiements réussis",
                value:
                  payments.isPending || payments.isError
                    ? "—"
                    : String(rows.filter((p) => p.status === "SUCCESS").length),
                icon: CheckCheck,
                note: "Sur les transactions chargées",
              },
            ].map((k, i) => (
              <Card key={k.label} className={"kpi kpi-" + i}>
                <div className="kpi-top">
                  <span>{k.label}</span>
                  <k.icon size={19} />
                </div>
                <strong>{k.value}</strong>
                <small>{k.note}</small>
              </Card>
            ))}
          </div>
          <div className="overview-grid">
            <Card className="activity-card">
              <div className="section-heading">
                <div>
                  <h2>Activité des transactions</h2>
                  <p>Montants par jour UTC · données chargées uniquement</p>
                </div>
                <Badge>EUR</Badge>
              </div>
              <div className="chart-legend">
                <span>
                  <i />
                  SUCCESS
                </span>
                <span>
                  <i className="purple" />
                  REJECTED
                </span>
              </div>
              {payments.isPending ? (
                <Skeleton />
              ) : payments.isError ? (
                <ErrorState
                  error={payments.error}
                  retry={() => payments.refetch()}
                />
              ) : (
                <ActivityChart payments={rows} />
              )}
            </Card>
            <Card className="resilience-card">
              <div className="section-heading">
                <h2>État de la plateforme</h2>
                <span className="live-label">LIVE CHECK</span>
              </div>
              <div className="platform-emblem">
                <Layers3 size={42} />
              </div>
              <h3>
                {health.data?.status === "ok"
                  ? "Le socle est connecté."
                  : "Connexion à vérifier."}
              </h3>
              <p>
                La banque est opérationnelle lorsque les API répondent. Les
                moteurs de résilience restent à intégrer.
              </p>
              <div className="service-row">
                <span>Payment API</span>
                <Badge tone={health.data?.status === "ok" ? "good" : "neutral"}>
                  {health.data?.status === "ok" ? "AVAILABLE" : "UNAVAILABLE"}
                </Badge>
              </div>
              <div className="service-row">
                <span>AI & Recovery</span>
                <Badge>NOT CONFIGURED</Badge>
              </div>
              <Link className="text-link" to="/infrastructure">
                Voir l’infrastructure <ArrowRight size={15} />
              </Link>
            </Card>
          </div>
          <Card className="recent">
            <div className="section-heading">
              <div>
                <h2>Dernières transactions</h2>
                <p>Les 5 premières transactions de l’historique chargé</p>
              </div>
              <Link className="text-link" to="/transactions">
                Tout consulter <ArrowRight size={15} />
              </Link>
            </div>
            {payments.isPending ? (
              <Skeleton />
            ) : payments.isError ? (
              <ErrorState error={payments.error} />
            ) : (
              <TransactionTable items={rows.slice(0, 5)} />
            )}
          </Card>
        </>
      ) : (
        <Card>
          <div className="empty">
            <h2>Espace de supervision</h2>
            <p>
              Le rôle {user?.role} ne dispose pas d’un accès bancaire global.
              Consultez la santé des API et les modules en préparation.
            </p>
            <Link className="button secondary" to="/infrastructure">
              Consulter l’infrastructure
            </Link>
          </div>
        </Card>
      )}
    </>
  );
}
