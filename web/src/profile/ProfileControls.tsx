// Shows the current CVD profile and lets the user set it by hand. Author: Iris.
// Screening fills the profile automatically; manual entry covers people who already
// know their type and lets us test the other views before scoring is ready.
import type { CVDProfile, CVDType } from "../api";

const TYPES: { value: CVDType; label: string }[] = [
  { value: "normal", label: "Normal" },
  { value: "protan", label: "Protan (red)" },
  { value: "deutan", label: "Deutan (green)" },
  { value: "tritan", label: "Tritan (blue)" },
];

interface ProfileControlsProps {
  profile: CVDProfile;
  onChange: (profile: CVDProfile) => void;
}

export function ProfileControls({ profile, onChange }: ProfileControlsProps) {
  const setType = (type: CVDType) => {
    // A "normal" profile must have severity 0 (CLAUDE.md Section 6).
    const severity = type === "normal" ? 0 : profile.severity || 1;
    onChange({ ...profile, type, severity });
  };

  return (
    <fieldset className="profile-controls">
      <legend>Your color vision</legend>
      <label>
        Type{" "}
        <select value={profile.type} onChange={(e) => setType(e.target.value as CVDType)}>
          {TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Severity{" "}
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          value={profile.type === "normal" ? 0 : profile.severity}
          disabled={profile.type === "normal"}
          onChange={(e) => onChange({ ...profile, severity: Number(e.target.value) })}
        />{" "}
        <output>{profile.severity.toFixed(2)}</output>
      </label>
      {profile.confidence < 1 && (
        <span className="muted">Screening confidence {Math.round(profile.confidence * 100)}%</span>
      )}
    </fieldset>
  );
}
