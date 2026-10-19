import { Link } from "react-router-dom";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { Payment } from "../../types/api";
import { Badge, Empty } from "../../components/ui";
import { date, money, shortId } from "../../utils/money";
export function TransactionTable({ items }: { items: Payment[] }) {
  if (!items.length)
    return (
      <Empty title="Aucune transaction">
        Votre historique apparaîtra après un premier virement.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Montant</th>
            <th>Statut</th>
            <th>Date</th>
            <th aria-label="Détails" />
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id}>
              <td>
                <div className="table-identity">
                  <span
                    className={`transfer-icon ${p.status === "REJECTED" ? "purple" : ""}`}
                  >
                    <ArrowUpRight size={18} />
                  </span>
                  <div>
                    <Link to={"/transactions/" + p.id}>
                      Virement EUR{" "}
                      <span className="mono">#{p.id.slice(0, 8)}</span>
                    </Link>
                    <small
                      title={`${p.source_account_id} → ${p.destination_account_id}`}
                    >
                      {shortId(p.source_account_id)} <ArrowDownLeft size={11} />{" "}
                      {shortId(p.destination_account_id)}
                    </small>
                  </div>
                </div>
              </td>
              <td className="amount">{money(p.amount_minor)}</td>
              <td>
                <Badge tone={p.status === "SUCCESS" ? "good" : "bad"}>
                  {p.status}
                </Badge>
              </td>
              <td className="muted nowrap">{date(p.created_at)}</td>
              <td>
                <Link
                  className="icon-link"
                  aria-label={"Détails " + p.id}
                  to={"/transactions/" + p.id}
                >
                  <ArrowUpRight size={18} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
