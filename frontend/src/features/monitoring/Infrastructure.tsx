import { Server, Activity, Database, Zap } from "lucide-react";
import { useHealth } from "../../hooks/useData";
import { Badge, Button, Card, PageTitle } from "../../components/ui";
import { date } from "../../utils/money";
function ServiceHealth({
  service,
  title,
  port,
}: {
  service: "auth" | "payment";
  title: string;
  port: number;
}) {
  const q = useHealth(service);
  return (
    <Card className="health-card">
      <div className="section-heading">
        <span className="account-symbol">
          <Server />
        </span>
        <Badge tone={q.data?.status === "ok" ? "good" : "neutral"}>
          {q.isPending
            ? "CHECKING"
            : q.data?.status === "ok"
              ? "AVAILABLE"
              : "UNAVAILABLE"}
        </Badge>
      </div>
      <h2>{title}</h2>
      <p>FastAPI · port interne {port}</p>
      <dl className="details">
        <dt>Santé</dt>
        <dd>{q.data?.status || "Non disponible"}</dd>
        <dt>Vérifié à</dt>
        <dd>{q.data ? date(q.data.checked_at) : "—"}</dd>
      </dl>
      {q.isError && <p className="field-error">{q.error.message}</p>}
      <Button
        variant="secondary"
        onClick={() => q.refetch()}
        disabled={q.isFetching}
      >
        Actualiser
      </Button>
    </Card>
  );
}
export function Infrastructure() {
  return (
    <>
      <PageTitle
        eyebrow="PLATFORM / INFRASTRUCTURE"
        title="La visibilité commence ici."
        description="Health checks réels, actualisés toutes les 30 secondes. Aucune télémétrie simulée."
      />
      <div className="two-columns">
        <ServiceHealth service="auth" title="Auth Service" port={8001} />
        <ServiceHealth service="payment" title="Payment API" port={8000} />
      </div>
      <Card className="section-space">
        <div className="section-heading">
          <h2>Observabilité à intégrer</h2>
          <Badge>NOT CONFIGURED</Badge>
        </div>
        <div className="future-grid">
          {[
            {
              name: "Prometheus",
              icon: Activity,
              text: "Séries temporelles et métriques CPU/RAM indisponibles.",
            },
            {
              name: "Grafana",
              icon: Zap,
              text: "Dashboards et analyses à connecter en phase 3.",
            },
            {
              name: "Loki",
              icon: Database,
              text: "Recherche dans les logs non connectée.",
            },
          ].map((s) => (
            <div className="future-tile" key={s.name}>
              <s.icon size={25} />
              <h3>{s.name}</h3>
              <p>{s.text}</p>
              <span className="unavailable-value">—</span>
            </div>
          ))}
        </div>
        <p className="fine-print">
          Les health checks des API vérifient PostgreSQL indirectement. Aucun
          endpoint de supervision directe de la base n’est exposé.
        </p>
      </Card>
    </>
  );
}
