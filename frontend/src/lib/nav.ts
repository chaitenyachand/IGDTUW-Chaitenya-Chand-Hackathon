import { useNavigate } from "@tanstack/react-router";

/** Loosely-typed navigation helper (route types regenerate when the dev server runs). */
export function useGo() {
  const navigate = useNavigate();
  return (to: string, search?: Record<string, string | number | undefined>) => {
    void navigate({ to, search } as never);
  };
}
