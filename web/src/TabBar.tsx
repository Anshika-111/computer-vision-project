// Bottom tab bar for the installed app (hidden in a browser tab, where the top nav shows).
// Author: Iris.
import { routeHref, type Route } from "./router";

interface Tab {
  route: Route;
  label: string;
  /** Stroke path on a 24×24 grid. */
  icon: string;
}

/** Small circle as a path, so every icon is one stroked <path>. */
const dot = (x: number, y: number, r: number) =>
  `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

const TABS: Tab[] = [
  { route: "home", label: "Home", icon: "M4 10.5L12 4l8 6.5V20h-5v-6h-6v6H4z" },
  {
    route: "screening",
    label: "Screening",
    icon: dot(12, 12, 9) + dot(9, 10, 1.3) + dot(14.5, 9, 1.3) + dot(15, 14.5, 1.3) + dot(9.5, 15, 1.3),
  },
  {
    route: "images",
    label: "Image",
    icon: "M3 5h18v14H3zM4 18l5-5 4 4 3-3 4 4" + dot(9, 10, 1.8),
  },
  { route: "live", label: "Live", icon: "M3 6h13v12H3zM16 10.5l5-3v9l-5-3" },
  { route: "games", label: "Study", icon: "M3 6h8v12H3zM13 6h8v12h-8z" },
];

/** The profile page belongs to the Home tab: it opens from the chip and the home steps. */
function tabFor(route: Route): Route {
  return route === "profile" || route === "welcome" ? "home" : route;
}

export function TabBar({ route }: { route: Route }) {
  const current = tabFor(route);
  return (
    <nav className="tab-bar" aria-label="Sections">
      {TABS.map((t) => (
        <a
          key={t.route}
          href={routeHref(t.route)}
          aria-current={t.route === current ? "page" : undefined}
        >
          <span className="tab-icon">
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24">
              <path d={t.icon} />
            </svg>
          </span>
          {t.label}
        </a>
      ))}
    </nav>
  );
}
