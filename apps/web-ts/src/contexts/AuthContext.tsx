import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchCurrentUser } from "@/lib/backend";

interface AppUser {
  email: string;
}

interface AppSession {
  user: AppUser;
}

interface AuthContextType {
  session: AppSession | null;
  user: AppUser | null;
  role: "employee" | "hr" | null;
  loading: boolean;
  signIn: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  user: null,
  role: null,
  loading: true,
  signIn: async () => {},
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AppSession | null>(null);
  const [user, setUser] = useState<AppUser | null>(null);
  const [role, setRole] = useState<"employee" | "hr" | null>(null);
  const [loading, setLoading] = useState(true);

  const STORAGE_KEY = "pinghr_user_email";

  const hydrateForEmail = useCallback(async (email: string) => {
    const profile = await fetchCurrentUser(email);
    const normalized = profile.role.toUpperCase();
    const mappedRole: "employee" | "hr" =
      normalized === "HR" || normalized === "MANAGER" ? "hr" : "employee";

    const appUser = { email: profile.email };
    setUser(appUser);
    setSession({ user: appUser });
    setRole(mappedRole);
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      const savedEmail = localStorage.getItem(STORAGE_KEY);
      if (!savedEmail) {
        setLoading(false);
        return;
      }

      try {
        await hydrateForEmail(savedEmail);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
        setSession(null);
        setUser(null);
        setRole(null);
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, [hydrateForEmail]);

  const signIn = useCallback(
    async (email: string) => {
      setLoading(true);
      try {
        await hydrateForEmail(email);
        localStorage.setItem(STORAGE_KEY, email);
      } finally {
        setLoading(false);
      }
    },
    [hydrateForEmail]
  );

  const signOut = async () => {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setUser(null);
    setRole(null);
  };

  return (
    <AuthContext.Provider value={{ session, user, role, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
