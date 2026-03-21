import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type AuthState = {
  loading: boolean;
  session: { user: { email: string } } | null;
  role: "employee" | "hr" | null;
};

const authState: AuthState = {
  loading: false,
  session: null,
  role: null,
};

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/contexts/HRTicketsContext", () => ({
  HRTicketsProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/pages/Index", () => ({ default: () => <div>Index page</div> }));
vi.mock("@/pages/Chat", () => ({ default: () => <div>Employee chat page</div> }));
vi.mock("@/pages/HRChat", () => ({ default: () => <div>HR chat page</div> }));
vi.mock("@/pages/HROps", () => ({ default: () => <div>HR ops page</div> }));
vi.mock("@/pages/AuditLog", () => ({ default: () => <div>Audit log page</div> }));
vi.mock("@/pages/Auth", () => ({ default: () => <div>Auth page</div> }));
vi.mock("@/pages/NotFound", () => ({ default: () => <div>Not found page</div> }));

import App from "@/App";

describe("App route guards", () => {
  beforeEach(() => {
    authState.loading = false;
    authState.session = null;
    authState.role = null;
    window.history.pushState({}, "", "/");
  });

  it("redirects unauthenticated employees to auth", async () => {
    window.history.pushState({}, "", "/chat");

    render(<App />);

    expect(await screen.findByText("Auth page")).toBeInTheDocument();
  });

  it("redirects hr users away from employee chat", async () => {
    authState.session = { user: { email: "jordan.lee@acme.com" } };
    authState.role = "hr";
    window.history.pushState({}, "", "/chat");

    render(<App />);

    expect(await screen.findByText("HR ops page")).toBeInTheDocument();
  });

  it("redirects employees away from hr-only routes", async () => {
    authState.session = { user: { email: "alex.kim@acme.com" } };
    authState.role = "employee";
    window.history.pushState({}, "", "/hr-chat");

    render(<App />);

    expect(await screen.findByText("Employee chat page")).toBeInTheDocument();
  });

  it("renders the requested protected page when auth matches", async () => {
    authState.session = { user: { email: "alex.kim@acme.com" } };
    authState.role = "employee";
    window.history.pushState({}, "", "/chat");

    render(<App />);

    expect(await screen.findByText("Employee chat page")).toBeInTheDocument();
  });
});
