"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { businessApi } from "@/lib/api/endpoints";
import type { Business, BusinessProfile } from "@/types/api";
import { useSession } from "../session";

export function emptyProfile(name: string): BusinessProfile {
  return {
    name,
    industry: null,
    description: null,
    location: null,
    website: null,
    preferred_language: "en",
    audience: { description: null, customer_types: [], pain_points: [] },
    unique_selling_points: [],
    competitors: [],
    marketing_goals: [],
    topics_to_avoid: [],
  };
}

export function useBusiness() {
  const { workspace } = useSession();
  const queryClient = useQueryClient();
  const key = ["business", workspace.id];
  const query = useQuery({ queryKey: key, queryFn: () => businessApi.get(workspace.id) });
  const update = (fn: (b: Business) => Business) => queryClient.setQueryData<Business>(key, (b) => (b ? fn(b) : b));
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard", workspace.id] });
  };
  return { ...query, workspaceId: workspace.id, update, refresh, canManage: workspace.role === "owner" || workspace.role === "admin" };
}
