import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect } from "react";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";

const fetchCurrentUser = vi.hoisted(() => vi.fn());

vi.mock("@/lib/backend", () => ({
  fetchCurrentUser,
}));

function AuthProbe() {
  const { session, user, role, loading, signIn, signOut } = useAuth();

  useEffect(() => {
    (window as typeof window & { authProbe?: unknown }).authProbe = {
      session,
      user,
      role,
      loading,
      signIn,
      signOut,
    };
  }, [session, user, role, loading, signIn, signOut]);

  return (
    <div>
      <span>{loading ? "loading" : "ready"}</span>
      <span>{session ? session.user.email : "no-session"}</span>
      <span>{user ? user.email : "no-user"}</span>
      <span>{role ?? "no-role"}</span>
    </div>
  );
}

function renderAuth() {
  return render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  fetchCurrentUser.mockReset();
  delete (window as typeof window & { authProbe?: unknown }).authProbe;
});

describe("AuthContext", () => {
  it("starts ready with no session when no saved email exists", async () => {
    renderAuth();

    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());
    expect(fetchCurrentUser).not.toHaveBeenCalled();
    expect(screen.getByText("no-session")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
    expect(screen.getByText("no-role")).toBeInTheDocument();
  });

  it("bootstraps from localStorage and maps manager role to hr", async () => {
    localStorage.setItem("pinghr_user_email", "jordan.lee@acme.com");
    fetchCurrentUser.mockResolvedValue({
      employee_id: 1,
      name: "Jordan Lee",
      email: "jordan.lee@acme.com",
      role: "MANAGER",
      direct_reports_count: 3,
    });

    renderAuth();

    expect(screen.getByText("loading")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());
    expect(screen.getAllByText("jordan.lee@acme.com")).toHaveLength(2);
    expect(screen.getByText("hr")).toBeInTheDocument();
    expect(fetchCurrentUser).toHaveBeenCalledWith("jordan.lee@acme.com");
    expect(localStorage.getItem("pinghr_user_email")).toBe("jordan.lee@acme.com");
  });

  it("maps non-hr roles to employee and stores the signed-in email", async () => {
    fetchCurrentUser.mockResolvedValue({
      employee_id: 2,
      name: "Alex Kim",
      email: "alex.kim@acme.com",
      role: "EMPLOYEE",
      direct_reports_count: 0,
    });

    renderAuth();

    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());

    const probe = (window as typeof window & { authProbe: any }).authProbe;
    await act(async () => {
      await probe.signIn("alex.kim@acme.com");
    });

    expect(fetchCurrentUser).toHaveBeenLastCalledWith("alex.kim@acme.com");
    expect(localStorage.getItem("pinghr_user_email")).toBe("alex.kim@acme.com");
    await waitFor(() => expect(screen.getByText("employee")).toBeInTheDocument());
    expect(screen.getAllByText("alex.kim@acme.com")).toHaveLength(2);
  });

  it("does not persist the email when signIn fails", async () => {
    fetchCurrentUser.mockRejectedValue(new Error("sign-in failed"));

    renderAuth();
    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());

    const probe = (window as typeof window & { authProbe: any }).authProbe;
    await expect(
      act(async () => {
        await probe.signIn("alex.kim@acme.com");
      })
    ).rejects.toThrow("sign-in failed");

    expect(localStorage.getItem("pinghr_user_email")).toBeNull();
    expect(screen.getByText("no-session")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
    expect(screen.getByText("no-role")).toBeInTheDocument();
  });

  it("clears session state when bootstrap hydration fails", async () => {
    localStorage.setItem("pinghr_user_email", "broken@acme.com");
    fetchCurrentUser.mockRejectedValue(new Error("bad token"));

    renderAuth();

    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());

    expect(screen.getByText("no-session")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
    expect(screen.getByText("no-role")).toBeInTheDocument();
    expect(localStorage.getItem("pinghr_user_email")).toBeNull();
  });

  it("signs out by clearing localStorage and resetting state", async () => {
    fetchCurrentUser.mockResolvedValue({
      employee_id: 3,
      name: "Alex Kim",
      email: "alex.kim@acme.com",
      role: "EMPLOYEE",
      direct_reports_count: 0,
    });

    renderAuth();
    await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());

    const probe = (window as typeof window & { authProbe: any }).authProbe;
    await act(async () => {
      await probe.signIn("alex.kim@acme.com");
    });
    await act(async () => {
      await probe.signOut();
    });

    expect(localStorage.getItem("pinghr_user_email")).toBeNull();
    expect(screen.getByText("no-session")).toBeInTheDocument();
    expect(screen.getByText("no-user")).toBeInTheDocument();
    expect(screen.getByText("no-role")).toBeInTheDocument();
  });
});
