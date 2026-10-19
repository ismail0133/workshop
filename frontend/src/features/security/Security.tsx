import { ShieldCheck, ShieldAlert, ScrollText } from "lucide-react";
import { Badge, Card, Empty, PageTitle } from "../../components/ui";
export function Security() {
  return (
    <>
      <PageTitle
        eyebrow="RESILIENCE / SECURITY"
        title="Security Center."
        description="Le futur point de convergence de vos signaux de sécurité."
        action={<Badge>NOT CONFIGURED</Badge>}
      />
      <div className="two-columns">
        {[
          {
            name: "Web Application Firewall",
            icon: ShieldCheck,
            text: "Le WAF n’est pas encore intégré. Aucun filtrage actif revendiqué.",
          },
          {
            name: "SIEM / SOC",
            icon: ShieldAlert,
            text: "Le pipeline de collecte et de corrélation reste à connecter.",
          },
        ].map((x) => (
          <Card key={x.name}>
            <x.icon className="feature-icon" size={30} />
            <h2>{x.name}</h2>
            <p>{x.text}</p>
            <Badge>NOT CONFIGURED</Badge>
          </Card>
        ))}
      </div>
      <Card className="section-space">
        <div className="section-heading">
          <h2>Alertes & événements</h2>
          <ScrollText size={20} />
        </div>
        <Empty title="En attente du service de sécurité">
          Aucune alerte disponible. L’absence de données ne signifie pas
          l’absence de menace.
        </Empty>
      </Card>
    </>
  );
}
