// App shell: shared CVD profile plus the Screening, Images, and Live tabs. Author: Iris.
import { useState } from "react";

import type { CVDProfile } from "./api";
import { ImageView } from "./images/ImageView";
import { LiveMode } from "./live/LiveMode";
import { ProfileControls } from "./profile/ProfileControls";
import { ScreeningView } from "./screening/ScreeningView";

type Tab = "screening" | "images" | "live";

const TABS: { value: Tab; label: string }[] = [
  { value: "screening", label: "Screening" },
  { value: "images", label: "Images" },
  { value: "live", label: "Live camera" },
];

const DEFAULT_PROFILE: CVDProfile = { type: "deutan", severity: 1, confidence: 1 };

export function App() {
  const [tab, setTab] = useState<Tab>("screening");
  const [profile, setProfile] = useState<CVDProfile>(DEFAULT_PROFILE);

  return (
    <main>
      <h1>ChromaFix</h1>
      <ProfileControls profile={profile} onChange={setProfile} />
      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.value}
            aria-current={tab === t.value ? "page" : undefined}
            onClick={() => setTab(t.value)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "screening" && <ScreeningView onScored={setProfile} />}
      {tab === "images" && <ImageView profile={profile} />}
      {tab === "live" && <LiveMode profile={profile} />}
    </main>
  );
}
