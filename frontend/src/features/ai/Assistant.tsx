import { Bot, BookOpen, Send } from "lucide-react";
import { Badge, Button, Card, Empty, PageTitle } from "../../components/ui";
export type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  references: { title: string; href: string }[];
};
export function MessageList({
  messages,
  loading = false,
  error,
}: {
  messages: AssistantMessage[];
  loading?: boolean;
  error?: string;
}) {
  return (
    <div aria-live="polite">
      {messages.map((m) => (
        <article className={"chat-message " + m.role} key={m.id}>
          <strong>{m.role === "user" ? "Vous" : "Assistant"}</strong>
          <p>{m.content}</p>
          {m.references.map((r) => (
            <span key={r.href} className="reference">
              <BookOpen size={14} />
              {r.title}
            </span>
          ))}
        </article>
      ))}
      {loading && <p role="status">Recherche documentaire en cours…</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
export function Assistant() {
  return (
    <>
      <PageTitle
        eyebrow="INTELLIGENCE / AI ASSISTANT"
        title="La connaissance, à portée de main."
        description="Votre futur assistant documentaire, avec références vérifiables."
        action={<Badge>NOT CONFIGURED</Badge>}
      />
      <Card className="assistant-card">
        <div className="assistant-empty">
          <span className="assistant-icon">
            <Bot size={36} />
          </span>
          <Empty title="Votre assistant se prépare">
            Le service RAG sera intégré lors d’une prochaine phase. Les réponses
            et leurs références apparaîtront ici après connexion du backend.
          </Empty>
        </div>
        <MessageList messages={[]} />
        <form onSubmit={(e) => e.preventDefault()} className="chat-composer">
          <label className="sr-only" htmlFor="question">
            Votre question
          </label>
          <textarea
            id="question"
            placeholder="L’assistant sera disponible après l’intégration du service RAG…"
            disabled
          />
          <Button disabled aria-label="Envoyer la question">
            <Send size={18} />
          </Button>
        </form>
        <p className="fine-print">
          Aucune réponse générée. Aucun accès aux opérations bancaires.
        </p>
      </Card>
    </>
  );
}
