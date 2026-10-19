import { BrainCircuit } from "lucide-react";
import { Badge, Card, Empty, PageTitle } from "../../components/ui";
export function Detection() {
  return (
    <>
      <PageTitle
        eyebrow="INTELLIGENCE / AI DETECTION"
        title="Comprendre les signaux faibles."
        description="Interface destinée au futur moteur Isolation Forest."
        action={<Badge>NOT CONFIGURED</Badge>}
      />
      <div className="kpi-grid">
        {[
          "Score d’anomalie",
          "Version du modèle",
          "Dernière inférence",
          "Détections",
        ].map((label) => (
          <Card className="kpi" key={label}>
            <p>{label}</p>
            <strong>—</strong>
            <small>Non disponible</small>
          </Card>
        ))}
      </div>
      <Card>
        <BrainCircuit className="feature-icon" size={32} />
        <Empty title="Le moteur de détection n’est pas connecté">
          Les scores et leur historique apparaîtront après intégration du
          modèle. Aucun score simulé.
        </Empty>
      </Card>
    </>
  );
}
