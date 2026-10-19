export const recoveryStates = [
  "DETECTED",
  "ANALYZING",
  "CONFIRMED",
  "REJECTED",
  "REMEDIATING",
  "VALIDATING",
  "RECOVERED",
  "RECOVERY_FAILED",
] as const;
export type RecoveryEvent = {
  id: string;
  state: (typeof recoveryStates)[number];
  occurredAt: string;
  description: string;
};
export function Timeline({ events }: { events: RecoveryEvent[] }) {
  return events.length ? (
    <ol className="timeline">
      {events.map((e) => (
        <li key={e.id}>
          <strong>{e.state}</strong>
          <time dateTime={e.occurredAt}>
            {new Date(e.occurredAt).toLocaleString("fr-FR")}
          </time>
          <p>{e.description}</p>
        </li>
      ))}
    </ol>
  ) : (
    <p className="muted">
      Aucun événement disponible : service d’incidents non connecté.
    </p>
  );
}
