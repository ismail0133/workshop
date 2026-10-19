import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight, ShieldCheck, Layers3, LockKeyhole } from "lucide-react";
import { useAuth } from "./AuthProvider";
import { Alert, Button, Input } from "../../components/ui";
const schema = z.object({
  email: z.email("Adresse e-mail invalide."),
  password: z.string().min(1, "Le mot de passe est requis.").max(128),
});
export function Login() {
  const auth = useAuth();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  if (auth.user) return <Navigate to="/" replace />;
  return (
    <main className="login">
      <section className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <Layers3 />
          </span>
          RESILIENCE<span className="brand-alpha">ALPHA</span>
        </div>
        <div className="login-copy">
          <div className="eyebrow">BANKING & CYBER RESILIENCE</div>
          <h1>
            La confiance.
            <br />À chaque
            <br />
            <span>transaction.</span>
          </h1>
          <p>
            Un espace de contrôle unifié pour vos opérations bancaires et votre
            résilience numérique.
          </p>
          <div className="orbit">
            <div className="orbit-inner">
              <ShieldCheck size={58} />
            </div>
            <span className="orbit-label">TRANSACTION INTEGRITY</span>
          </div>
        </div>
        <p className="login-foot">
          EPSI WORKSHOP <span>ENVIRONNEMENT FICTIF</span>
        </p>
      </section>
      <section className="login-panel">
        <div className="login-form">
          <BadgeLogo />
          <div className="eyebrow">VOTRE ESPACE SÉCURISÉ</div>
          <h2>Heureux de vous retrouver.</h2>
          <p>Connectez-vous à votre centre de contrôle.</p>
          {(error || auth.reason) && <Alert>{error || auth.reason}</Alert>}
          <form
            onSubmit={handleSubmit(async (values) => {
              setError("");
              try {
                await auth.login(values.email, values.password);
              } catch (e) {
                setError((e as Error).message);
              }
            })}
            noValidate
          >
            <label htmlFor="email">Adresse e-mail</label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              placeholder="vous@resilience.test"
              {...register("email")}
              aria-invalid={!!errors.email}
            />
            {errors.email && (
              <small className="field-error">{errors.email.message}</small>
            )}
            <label htmlFor="password">Mot de passe</label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
              aria-invalid={!!errors.password}
            />
            {errors.password && (
              <small className="field-error">{errors.password.message}</small>
            )}
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Connexion en cours…" : "Se connecter"}
              <ArrowRight size={18} />
            </Button>
          </form>
          <div className="login-note">
            <LockKeyhole size={16} />
            <span>
              Session de 15 minutes. Aucun jeton conservé dans le stockage du
              navigateur.
            </span>
          </div>
          <p className="fine-print">
            Données bancaires fictives • Accès réservé au laboratoire
          </p>
        </div>
      </section>
    </main>
  );
}
function BadgeLogo() {
  return (
    <div className="small-shield">
      <ShieldCheck size={25} />
    </div>
  );
}
