"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { authApi, workspaceApi } from "@/lib/api/endpoints";
import type { User, Workspace } from "@/types/api";

const WORKSPACE_KEY = "cf.workspace";

interface SessionValue {
  user: User;
  workspaces: Workspace[];
  workspace: Workspace;
  selectWorkspace: (id: string) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside <AppProviders>");
  return value;
}

function readStoredWorkspace(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null; // storage unavailable (private mode)
  }
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        // Auth failures are final once the client has tried a refresh; don't hammer the API.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  });
}

export function AppProviders({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const [client] = useState(makeClient);
  return (
    <QueryClientProvider client={client}>
      <SessionGate fallback={fallback}>{children}</SessionGate>
    </QueryClientProvider>
  );
}

function SessionGate({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useQuery({ queryKey: ["me"], queryFn: authApi.me });
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: workspaceApi.list, enabled: !!me.data });
  // Only read after data loads (the server renders the fallback), so no hydration mismatch.
  const [selected, setSelected] = useState<string | null>(readStoredWorkspace);

  const unauthenticated = me.error instanceof ApiError && me.error.status === 401;
  useEffect(() => {
    if (unauthenticated) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [unauthenticated, pathname, router]);

  const selectWorkspace = useCallback((id: string) => {
    setSelected(id);
    try {
      window.localStorage.setItem(WORKSPACE_KEY, id);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<SessionValue | null>(() => {
    if (!me.data || !workspaces.data?.length) return null;
    const workspace = workspaces.data.find((w) => w.id === selected) ?? workspaces.data[0]!;
    return { user: me.data, workspaces: workspaces.data, workspace, selectWorkspace };
  }, [me.data, workspaces.data, selected, selectWorkspace]);

  const failure = (me.error && !unauthenticated) || workspaces.error;
  if (failure) {
    return (
      <div className="grid min-h-dvh place-items-center px-6">
        <div className="grid max-w-sm gap-3 text-center">
          <p className="text-lg font-semibold">Your workspace didn&apos;t load</p>
          <p className="text-muted">
            {failure instanceof ApiError ? failure.message : "ContentFactory is unreachable right now."}
          </p>
          <button className="text-lab underline" onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
  if (workspaces.data && workspaces.data.length === 0) {
    return (
      <div className="grid min-h-dvh place-items-center px-6 text-center text-muted">
        Your account has no workspace. Contact support and we&apos;ll restore it.
      </div>
    );
  }
  if (!value) return <>{fallback}</>;
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
