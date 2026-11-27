// App shell: header with nav and profile chip, shared CVD profile, one page per route. Author: Iris.
import { useCallback, useEffect } from "react";

import type { CVDProfile } from "./api";
import { GamesView } from "./games/GamesView";
import { HomePage } from "./home/HomePage";
import { ImageView } from "./images/ImageView";
import { LiveMode } from "./live/LiveMode";
import { ProfilePage } from "./profile/ProfilePage";
import { profileLabel, useProfileStore } from "./profile/profileStore";
import { routeHref, useRoute, type Route } from "./router";
import { ScreeningView } from "./screening/ScreeningView";
import { WelcomePage } from "./welcome/WelcomePage";

const NAV: { route: Route; label: string }[] = [
  { route: "screening", label: "Screening" },
  { route: "images", label: "Image" },
  { route: "live", label: "Live" },
  { route: "games", label: "Study" },
];

const TITLES: Record<Route, string> = {
  welcome: "ChromaFix",
  home: "Home · ChromaFix",
  screening: "Screening · ChromaFix",
  profile: "Your profile · ChromaFix",
  images: "Recolor an image · ChromaFix",
  live: "Live webcam · ChromaFix",
  games: "Study games · ChromaFix",
};

export function App() {
  const route = useRoute();
  const [state, setState] = useProfileStore();
  const { profile, source } = state;

  useEffect(() => {
    document.title = TITLES[route];
  }, [route]);

  const onScored = useCallback(
    (scored: CVDProfile) => {
      setState({ profile: scored, source: "screening" });
      window.location.hash = routeHref("profile");
    },
    [setState],
  );

  if (route === "welcome") return <WelcomePage />;

  const chip = source === "example" ? "No profile yet" : profileLabel(profile);

  return (
    <div className="app">
      <header className="app-header">
        <a className="wordmark" href={routeHref("home")}>
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
        <a
          className="profile-chip"
          data-empty={source === "example" || undefined}
          href={routeHref("profile")}
          aria-current={route === "profile" ? "page" : undefined}
          aria-label={`Your profile: ${chip}`}
        >
          {chip}
        </a>
      </header>
      <main className="app-main">
        {route === "home" && <HomePage profile={profile} source={source} />}
        {route === "screening" && <ScreeningView onScored={onScored} />}
        {route === "profile" && <ProfilePage state={state} onChange={setState} />}
        {route === "images" && <ImageView profile={profile} />}
        {route === "live" && <LiveMode profile={profile} />}
        {route === "games" && (
          <GamesView profile={profile} profileIsExample={source === "example"} />
        )}
      </main>
    </div>
  );
}
