import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { usePayments } from "../../hooks/useData";
import { api } from "../../services/api";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  PageTitle,
  Skeleton,
} from "../../components/ui";
import { TransactionTable } from "./TransactionTable";
import { date, money } from "../../utils/money";
export function Transactions() {
  const q = usePayments();
  const items = q.data?.pages.flatMap((p) => p.items) || [];
  return (
    <>
      <PageTitle
        eyebrow="BANKING / TRANSACTIONS"
        title="Chaque mouvement, traçable."
        description="L’historique autorisé, du plus récent au plus ancien."
      />
      <Card>
        <div className="section-heading">
          <h2>Historique des transactions</h2>
          <Badge>{items.length} CHARGÉES</Badge>
        </div>
        {q.isPending ? (
          <Skeleton />
        ) : q.isError ? (
          <ErrorState error={q.error} retry={() => q.refetch()} />
        ) : (
          <TransactionTable items={items} />
        )}
        <div className="table-footer">
          <p>
            {q.hasNextPage
              ? "Historique partiel · d’autres résultats sont disponibles."
              : "Fin des résultats récupérés."}
          </p>
          {q.hasNextPage && (
            <Button
              variant="secondary"
              onClick={() => q.fetchNextPage()}
              disabled={q.isFetchingNextPage}
            >
              {q.isFetchingNextPage
                ? "Chargement…"
                : "Charger la page suivante"}
            </Button>
          )}
        </div>
      </Card>
    </>
  );
}
export function TransactionDetail() {
  const { id } = useParams();
  const q = useQuery({
    queryKey: ["payment", id],
    queryFn: () => api.payment(id!),
  });
  return (
    <>
      <PageTitle
        eyebrow="BANKING / TRANSACTIONS / DETAIL"
        title="Détail de la transaction."
        description="Résultat enregistré par le service bancaire."
        action={
          <Link className="button secondary" to="/transactions">
            Retour à l’historique
          </Link>
        }
      />
      <Card>
        {q.isPending ? (
          <Skeleton />
        ) : q.isError ? (
          <ErrorState error={q.error} retry={() => q.refetch()} />
        ) : (
          q.data && (
            <>
              <Badge tone={q.data.status === "SUCCESS" ? "good" : "bad"}>
                {q.data.status}
              </Badge>
              <h2 className="confirm-amount">{money(q.data.amount_minor)}</h2>
              <dl className="details">
                <dt>Identifiant</dt>
                <dd>{q.data.id}</dd>
                <dt>Compte source</dt>
                <dd>{q.data.source_account_id}</dd>
                <dt>Compte destinataire</dt>
                <dd>{q.data.destination_account_id}</dd>
                <dt>Date</dt>
                <dd>{date(q.data.created_at)}</dd>
                <dt>Code de rejet</dt>
                <dd>{q.data.failure_code || "Aucun"}</dd>
              </dl>
            </>
          )
        )}
      </Card>
    </>
  );
}
