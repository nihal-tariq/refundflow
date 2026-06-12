/** React Query hook for the backend health endpoint. */

import { useQuery } from "@tanstack/react-query";

interface Health {
  status: string;
  service: string;
  version: string;
  llm_enabled: boolean;
  llm_provider: string;
}

/** Poll the backend health endpoint for the connection indicator. */
export function useHealth() {
  return useQuery<Health>({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await fetch("/health");
      if (!res.ok) throw new Error("unhealthy");
      return res.json();
    },
    refetchInterval: 10000,
    retry: false,
  });
}
