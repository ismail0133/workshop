import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../services/api";
import { onSessionExpired, setSessionToken } from "../../services/http";
import type { User } from "../../types/api";
type Auth = {
  user: User | null;
  reason: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [reason, setReason] = useState("");
  const [expires, setExpires] = useState<number | null>(null);
  const client = useQueryClient();
  const clear = useCallback(
    (message = "") => {
      setSessionToken(null);
      setUser(null);
      setExpires(null);
      setReason(message);
      client.clear();
    },
    [client],
  );
  useEffect(
    () =>
      onSessionExpired(() =>
        clear("Votre session a expiré. Reconnectez-vous."),
      ),
    [clear],
  );
  useEffect(() => {
    if (!expires) return;
    const check = () => {
      if (Date.now() >= expires)
        clear("Votre session a expiré. Reconnectez-vous.");
    };
    const timer = setTimeout(check, Math.max(0, expires - Date.now()));
    window.addEventListener("focus", check);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("focus", check);
    };
  }, [expires, clear]);
  async function login(email: string, password: string) {
    clear();
    const result = await api.login(email, password);
    setSessionToken(result.access_token);
    try {
      const current = await api.me();
      setUser(current);
      setExpires(Date.now() + result.expires_in * 1000);
    } catch (error) {
      clear();
      throw error;
    }
  }
  return (
    <Context.Provider value={{ user, reason, login, logout: () => clear() }}>
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("Auth provider missing");
  return value;
}
export const canBank = (user: User | null) =>
  user?.role === "USER" || user?.role === "VALIDATOR";
