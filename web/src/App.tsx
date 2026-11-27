// App shell: header with nav and profile chip, shared CVD profile, one page per route. Author: Iris.
import { useEffect, useState } from "react";

import type { CVDProfile } from "./api";
import { GamesView } from "./games/GamesView";
import { ImageView } from "./images/ImageView";
import { LiveMode } from "./live/LiveMode";
import { ProfileControls } from "./profile/ProfileControls";
import { routeHref, useRoute, type Route } from "./router";
import { ScreeningView } from "./screening/ScreeningView";

const NAV: { route: Route; label: string; title: string }[] = [
  { route: "screening", label: "Screening", title: "Screening" },
  { route: "images", label: "Image", title: "Recolor an image" },
  { route: "live", label: "Live", title: "Live webcam" },
  { route: "games", label: "Study", title: "Study games" },
];

const DEFAULT_PROFILE: CVDProfile = { type: "deutan", severity: 1, confidence: 1 };

function profileLabel(profile: CVDProfile): string {
  if (profile.type === "normal") return "Normal vision";
  const type = profile.type.charAt(0).toUpperCase() + profile.type.slice(1);
  return `${type} · ${profile.severity.toFixed(1)}`;
}

export function App() {
  const route = useRoute();
  const [profile, setProfile] = useState<CVDProfile>(DEFAULT_PROFILE);

  const page = NAV.find((n) => n.route === route);
  useEffect(() => {
    document.title = page ? `${page.title} · ChromaFix` : "ChromaFix";
  }, [page]);

  return (
    <div className="app">
      <header className="app-header">
        <a className="wordmark" href={routeHref("screening")}>
          ChromaFix
        </a>
        <nav className="app-nav" aria-label="Sections">
          {NAV.map((n) => (
            <a
              key={n.route}
              href={routeHref(n.route)}
              aria-current={route === n.route ? "page" : undefined}
            >
              {n.label}
            </a>
          ))}
        </nav>
        <span className="profile-chip" aria-label={`Your profile: ${profileLabel(profile)}`}>
          {profileLabel(profile)}
        </span>
      </header>
      <main className="app-main">
        <ProfileControls profile={profile} onChange={setProfile} />
        {route === "screening" && <ScreeningView onScored={setProfile} />}
        {route === "images" && <ImageView profile={profile} />}
        {route === "live" && <LiveMode profile={profile} />}
        {route === "games" && <GamesView profile={profile} />}
      </main>
    </div>
  );
}
