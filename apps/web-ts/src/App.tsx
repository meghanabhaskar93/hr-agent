import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { useAuth } from "@/contexts/AuthContext";
import { HRTicketsProvider } from "@/contexts/HRTicketsContext";
import Index from "./pages/Index";
import Chat from "./pages/Chat";
import HRChat from "./pages/HRChat";
import HROps from "./pages/HROps";
import AuditLog from "./pages/AuditLog";
import Auth from "./pages/Auth";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

function RequireEmployee({ children }: { children: JSX.Element }) {
  const { loading, session, role } = useAuth();
  if (loading) return null;
  if (!session) return <Navigate to="/auth" replace />;
  if (role === "hr") return <Navigate to="/hr-ops" replace />;
  return children;
}

function RequireHR({ children }: { children: JSX.Element }) {
  const { loading, session, role } = useAuth();
  if (loading) return null;
  if (!session) return <Navigate to="/auth" replace />;
  if (role !== "hr") return <Navigate to="/chat" replace />;
  return children;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <HRTicketsProvider>
            <Routes>
              <Route path="/auth" element={<Auth />} />
              <Route path="/" element={<Index />} />
              <Route
                path="/chat"
                element={
                  <RequireEmployee>
                    <Chat />
                  </RequireEmployee>
                }
              />
              <Route
                path="/hr-chat"
                element={
                  <RequireHR>
                    <HRChat />
                  </RequireHR>
                }
              />
              <Route
                path="/hr-ops"
                element={
                  <RequireHR>
                    <HROps />
                  </RequireHR>
                }
              />
              <Route
                path="/hr-queue"
                element={
                  <RequireHR>
                    <Navigate to="/hr-ops" replace />
                  </RequireHR>
                }
              />
              <Route
                path="/audit-log"
                element={
                  <RequireHR>
                    <AuditLog />
                  </RequireHR>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </HRTicketsProvider>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
