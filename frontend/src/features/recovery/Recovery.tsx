import { Workflow } from "lucide-react";
import { Badge, Card, Empty, PageTitle } from "../../components/ui";
import { Timeline, recoveryStates } from "./Timeline";
export function Recovery() {
  return (
    <>
      <PageTitle
        eyebrow="RESILIENCE / AUTONOMOUS RECOVERY"
        title="De l’incident à la reprise."
        description="Suivi des incidents, actions correctives et preuves de récupération."
        action={<Badge>NOT CONFIGURED</Badge>}
      />
      <Card>
        <Workflow className="feature-icon" size={32} />
        <Empty title="Orchestrateur de reprise non connecté">
          Aucun incident ni action de remédiation disponible. Le temps de
          reprise ne peut pas encore être calculé.
        </Empty>
        <Timeline events={[]} />
      </Card>
      <Card className="section-space">
        <h2>Cycle de vie prévu</h2>
        <p>
          Référence de conception uniquement : aucun de ces états n’est
          actuellement observé.
        </p>
        <div className="state-flow">
          {recoveryStates.map((s) => (
            <Badge key={s}>{s}</Badge>
          ))}
        </div>
      </Card>
    </>
  );
}
