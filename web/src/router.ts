// Tiny hash router so each page has its own URL (#images, #live, ...). Author: Iris.
// Hash routing needs no server config and no extra dependency.
import { useEffect, useState } from "react";

export const ROUTES = ["screening", "images", "live", "games"] as const;
export type Route = (typeof ROUTES)[number];

export const DEFAULT_ROUTE: Route = "screening";

/** Map a location hash like "#live" to a known route, or the default. */
export function parseRoute(hash: string): Route {
  const name = hash.replace(/^#\/?/, "");
  return (ROUTES as readonly string[]).includes(name) ? (name as Route) : DEFAULT_ROUTE;
}

export function routeHref(route: Route): string {
  return `#${route}`;
}

/** Current route, kept in sync with the address bar (back/forward work). */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
