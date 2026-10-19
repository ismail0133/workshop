import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth, canBank } from "./features/auth/AuthProvider";
import { Login } from "./features/auth/Login";
import { Layout } from "./components/layout/Layout";
import { Overview } from "./features/dashboard/Overview";
import { Accounts } from "./features/accounts/Accounts";
import { Payments } from "./features/payments/Payments";
import {
  Transactions,
  TransactionDetail,
} from "./features/transactions/Transactions";
import { Infrastructure } from "./features/monitoring/Infrastructure";
import { Security } from "./features/security/Security";
import { Detection } from "./features/ai/Detection";
import { Recovery } from "./features/recovery/Recovery";
import { Assistant } from "./features/ai/Assistant";
import { Card, Empty } from "./components/ui";
export function Protected() {
  return useAuth().user ? <Outlet /> : <Navigate to="/login" replace />;
}
function BankRoute() {
  return canBank(useAuth().user) ? (
    <Outlet />
  ) : (
    <Card>
      <Empty title="Accès bancaire non autorisé">
        Votre rôle ne permet pas de consulter les comptes ou de créer un
        paiement.
      </Empty>
    </Card>
  );
}
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route element={<BankRoute />}>
            <Route path="accounts" element={<Accounts />} />
            <Route path="payments" element={<Payments />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="transactions/:id" element={<TransactionDetail />} />
          </Route>
          <Route path="infrastructure" element={<Infrastructure />} />
          <Route path="security" element={<Security />} />
          <Route path="ai-detection" element={<Detection />} />
          <Route path="recovery" element={<Recovery />} />
          <Route path="assistant" element={<Assistant />} />
          <Route
            path="*"
            element={
              <Card>
                <Empty title="Page introuvable">
                  Utilisez la navigation pour retrouver votre espace.
                </Empty>
              </Card>
            }
          />
        </Route>
      </Route>
    </Routes>
  );
}
