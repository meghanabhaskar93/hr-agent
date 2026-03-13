import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function Index() {
  const { role, loading, session } = useAuth();

  if (loading) return null;

  if (!session || !role) {
    return <Navigate to="/auth" replace />;
  }

  // HR users go to HR Ops dashboard, employees go to regular Chat
  if (role === "hr") {
    return <Navigate to="/hr-ops" replace />;
  }

  return <Navigate to="/chat" replace />;
}
