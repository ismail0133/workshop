import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CreditCard, ArrowUpRight } from "lucide-react";
import { useAccounts } from "../../hooks/useData";
import { api } from "../../services/api";
import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorState,
  Modal,
  PageTitle,
  Skeleton,
} from "../../components/ui";
import { money, date } from "../../utils/money";
export function Accounts() {
  const query = useAccounts();
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["account", selected],
    queryFn: () => api.account(selected!),
    enabled: !!selected,
  });
  const items = query.data?.pages.flatMap((p) => p.items) || [];
  return (
    <>
      <PageTitle
        eyebrow="BANKING / ACCOUNTS"
        title="Vos comptes, en un regard."
        description="Uniquement les comptes autorisés pour votre identité."
      />
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : !items.length ? (
        <Card>
          <Empty title="Aucun compte accessible" />
        </Card>
      ) : (
        <div className="account-grid">
          {items.map((a) => (
            <Card key={a.id} className="account-card">
              <div className="section-heading">
                <span className="account-symbol">
                  <CreditCard />
                </span>
                <Badge tone={a.status === "ACTIVE" ? "good" : "bad"}>
                  {a.status}
                </Badge>
              </div>
              <p>
                {a.is_synthetic
                  ? "COMPTE SYNTHÉTIQUE"
                  : "COMPTE DE DÉMONSTRATION"}
              </p>
              <h2>{a.label}</h2>
              <strong className="account-balance">
                {money(a.balance_minor)}
              </strong>
              <span className="muted">
                Solde fictif disponible • {a.currency}
              </span>
              <div className="account-bottom">
                <code>{a.id}</code>
                <Button
                  variant="ghost"
                  onClick={() => setSelected(a.id)}
                  aria-label={"Détails " + a.label}
                >
                  <ArrowUpRight size={20} />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {query.hasNextPage && (
        <Button
          variant="secondary"
          disabled={query.isFetchingNextPage}
          onClick={() => query.fetchNextPage()}
        >
          Charger plus de comptes
        </Button>
      )}
      {selected && (
        <Modal title="Détail du compte" onClose={() => setSelected(null)}>
          {detail.isPending ? (
            <Skeleton />
          ) : detail.isError ? (
            <ErrorState error={detail.error} />
          ) : (
            detail.data && (
              <dl className="details">
                <dt>Nom</dt>
                <dd>{detail.data.label}</dd>
                <dt>Identifiant</dt>
                <dd>{detail.data.id}</dd>
                <dt>Solde</dt>
                <dd>{money(detail.data.balance_minor)}</dd>
                <dt>Dernière modification</dt>
                <dd>{date(detail.data.updated_at)}</dd>
              </dl>
            )
          )}
        </Modal>
      )}
    </>
  );
}
