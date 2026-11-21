import { useEffect, useRef, useSyncExternalStore } from "react";

const eventName = "workbench-navigation";
function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener(eventName, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(eventName, callback);
  };
}

export function useWorkspaceQuery() {
  const search = useSyncExternalStore(subscribe, () => window.location.search);
  return new URLSearchParams(search);
}

export function workspaceHref(view: string, values: Record<string, string | null | undefined> = {}) {
  const query = new URLSearchParams({ view });
  for (const [key, value] of Object.entries(values)) if (value) query.set(key, value);
  return `?${query}`;
}

export function navigateWorkspace(view: string, values: Record<string, string | null | undefined> = {}, replace = false) {
  const href = workspaceHref(view, values);
  if (href === window.location.search) return;
  history[replace ? "replaceState" : "pushState"](null, "", href);
  window.dispatchEvent(new Event(eventName));
}

export function updateWorkspaceQuery(values: Record<string, string | null | undefined>, replace = false) {
  const query = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(values)) {
    if (value) query.set(key, value); else query.delete(key);
  }
  const view = query.get("view") ?? "reconciliation";
  query.delete("view");
  navigateWorkspace(view, Object.fromEntries(query), replace);
}


// A completed request may update its cache after navigation, but must not redirect
// the operator or clear the pending state of another workspace.
export function useWorkspaceActionGuard() {
  const lifecycle = useRef({ mounted: true, generation: 0 });
  useEffect(() => {
    lifecycle.current.mounted = true;
    return () => { lifecycle.current.mounted = false; lifecycle.current.generation += 1; };
  }, []);
  const capture = () => ({ search: window.location.search, generation: lifecycle.current.generation });
  const isCurrent = (origin: ReturnType<typeof capture> | undefined) => Boolean(origin && lifecycle.current.mounted && origin.generation === lifecycle.current.generation && origin.search === window.location.search);
  return { capture, isCurrent };
}
