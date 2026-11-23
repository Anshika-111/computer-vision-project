"""Ishihara-style screening plate generator and renderer. Author: Avneet.

Each target plate uses a figure color and a background color that differ only along the
target type's confusion direction (see simulate.confusion_direction). The step along that
direction is chosen so the pair drops to PLATE_HIDDEN_DE00 at the plate's design severity:
viewers of that type at or above it can no longer read the digit. Control plates differ in
lightness, so every viewer can read them.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from chromafix.color import (
    delta_e00,
    lab_to_linear,
    linear_to_lab,
    linear_to_srgb,
    srgb_to_linear,
    to_float,
    to_uint8,
)
from chromafix.constants import (
    CVD_TYPES,
    PLATE_DESIGN_SEVERITY,
    PLATE_HIDDEN_DE00,
    PLATE_MIN_NORMAL_DE00,
    SEED,
)
from chromafix.simulate import confusion_direction, simulate

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class Plate:
    """One screening plate (JSON form in CLAUDE.md Section 7). Colors are linear RGB.

    Control plates have target_type "normal" and difficulty 0.
    fail_severity is empty until validate_plates() fills it.
    """

    plate_id: str
    target_type: str
    difficulty: int
    digit: int
    is_control: bool
    figure_rgb: RGB
    background_rgb: RGB
    fail_severity: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Full JSON form, including fail_severity (for data/plates/plates.json)."""
        return {
            "plate_id": self.plate_id,
            "target_type": self.target_type,
            "difficulty": self.difficulty,
            "digit": self.digit,
            "is_control": self.is_control,
            "figure_rgb": [round(float(x), 6) for x in self.figure_rgb],
            "background_rgb": [round(float(x), 6) for x in self.background_rgb],
            "fail_severity": dict(self.fail_severity),
        }

    def public_dict(self) -> dict:
        """Metadata safe to send to the browser: no fail_severity and no answer."""
        d = self.to_dict()
        for key in ("fail_severity", "digit", "figure_rgb", "background_rgb"):
            d.pop(key)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Plate:
        """Build a plate from its JSON form."""
        return cls(
            plate_id=d["plate_id"],
            target_type=d["target_type"],
            difficulty=int(d["difficulty"]),
            digit=int(d["digit"]),
            is_control=bool(d["is_control"]),
            figure_rgb=tuple(float(x) for x in d["figure_rgb"]),
            background_rgb=tuple(float(x) for x in d["background_rgb"]),
            fail_severity=dict(d.get("fail_severity", {})),
        )


def pair_contrast(fig: np.ndarray, bg: np.ndarray, cvd_type: str, severity: float) -> np.ndarray:
    """CIEDE2000 between simulated figure and background colors.

    Args:
        fig: Linear RGB, shape (..., 3).
        bg: Linear RGB, same shape.
        cvd_type: Viewer type ("normal", "protan", "deutan", "tritan").
        severity: Viewer severity, 0.0–1.0.

    Returns:
        CIEDE2000 values, shape (...).
    """
    return delta_e00(
        linear_to_lab(simulate(fig, cvd_type, severity)),
        linear_to_lab(simulate(bg, cvd_type, severity)),
    )


def _round(c: np.ndarray) -> RGB:
    """Round to 6 decimals so plates.json stores exactly the colors that were validated."""
    return tuple(round(float(x), 6) for x in c)


def _find_pair(cvd_type: str, design_severity: float, rng: np.random.Generator) -> tuple[RGB, RGB]:
    """Pick a background/figure pair on a confusion line that hides at design_severity."""
    v = confusion_direction(cvd_type)
    for _ in range(50):
        n = 256
        a = rng.uniform(0.04, 0.6, size=(n, 3))
        sign = np.where(rng.random(n) < 0.5, 1.0, -1.0)[:, None]
        d = v[None, :] * sign
        # Largest step that keeps the second color inside [0.02, 0.98].
        with np.errstate(divide="ignore", invalid="ignore"):
            up = np.where(d > 1e-9, (0.98 - a) / d, np.inf)
            down = np.where(d < -1e-9, (0.02 - a) / d, np.inf)
        kmax = np.minimum(up, down).min(axis=1)
        lo, hi = np.zeros(n), kmax.copy()
        hidden_at_max = pair_contrast(a, a + kmax[:, None] * d, cvd_type, design_severity)
        searchable = hidden_at_max > PLATE_HIDDEN_DE00
        for _ in range(25):  # binary search: contrast at design severity == hidden threshold
            mid = (lo + hi) / 2
            c = pair_contrast(a, a + mid[:, None] * d, cvd_type, design_severity)
            too_far = c > PLATE_HIDDEN_DE00
            hi = np.where(too_far, mid, hi)
            lo = np.where(too_far, lo, mid)
        k = np.where(searchable, lo, kmax)
        b = a + k[:, None] * d
        ok = (
            (kmax > 0.05)
            & (pair_contrast(a, b, "normal", 0.0) >= PLATE_MIN_NORMAL_DE00)
            & (pair_contrast(a, b, cvd_type, 1.0) <= PLATE_HIDDEN_DE00 + 1e-6)
        )
        idx = np.flatnonzero(ok)
        if idx.size:
            i = int(rng.choice(idx))
            return _round(b[i]), _round(a[i])
    raise RuntimeError(f"No valid color pair for {cvd_type} at severity {design_severity}")


def _control_pair(rng: np.random.Generator) -> tuple[RGB, RGB]:
    """Figure/background that differ in lightness, readable by every viewer."""
    hue = rng.uniform(0, 2 * np.pi)
    chroma = rng.uniform(5, 20)
    ab = chroma * np.array([np.cos(hue), np.sin(hue)])
    bg = lab_to_linear(np.array([rng.uniform(68, 76), *ab]))
    fig = lab_to_linear(np.array([rng.uniform(32, 40), *(ab * 0.6)]))
    return _round(fig), _round(bg)


def generate_plates(n_per_type_level: int, seed: int = SEED, *, n_controls: int = 6) -> list[Plate]:
    """Generate target plates for every type × difficulty level, plus control plates.

    Args:
        n_per_type_level: Plates per (CVD type, difficulty level) cell.
        seed: Random seed.
        n_controls: Number of control plates.

    Returns:
        Plates without fail_severity. Run validate_plates() next.
    """
    rng = np.random.default_rng(seed)
    plates: list[Plate] = []
    for i in range(n_controls):
        fig, bg = _control_pair(rng)
        plates.append(
            Plate(f"control_d0_{i:04d}", "normal", 0, int(rng.integers(0, 10)), True, fig, bg)
        )
    count = 0
    for cvd_type in CVD_TYPES:
        for level, design_severity in sorted(PLATE_DESIGN_SEVERITY[cvd_type].items()):
            for _ in range(n_per_type_level):
                fig, bg = _find_pair(cvd_type, design_severity, rng)
                plates.append(
                    Plate(
                        f"{cvd_type}_d{level}_{count:04d}",
                        cvd_type,
                        level,
                        int(rng.integers(0, 10)),
                        False,
                        fig,
                        bg,
                    )
                )
                count += 1
    return plates


def _digit_mask(digit: int, size: int) -> np.ndarray:
    """Boolean (size, size) mask of a centered, bold digit."""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=int(size * 0.62))
    draw.text(
        (size / 2, size / 2),
        str(digit),
        fill=255,
        font=font,
        anchor="mm",
        stroke_width=max(1, size // 40),
        stroke_fill=255,
    )
    return np.asarray(img) > 127


def render_plate(plate: Plate, size: int = 512) -> np.ndarray:
    """Draw a plate as a linear image. Deterministic for a given plate_id.

    Dots get random size and a random brightness jitter so the digit cannot be read from
    lightness alone.

    Args:
        plate: The plate to draw.
        size: Output width and height in pixels.

    Returns:
        Linear RGB, float32, shape (size, size, 3).
    """
    rng = np.random.default_rng(SEED + zlib.crc32(plate.plate_id.encode()))
    ss = 2  # supersampling for smooth dot edges
    big = size * ss
    mask = _digit_mask(plate.digit, big)
    center, radius = big / 2, big * 0.48
    r_min, r_max = big * 0.007, big * 0.022
    cell = 2 * r_max
    grid: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    dots: list[tuple[float, float, float]] = []
    for _ in range(25000):
        r = r_min + (r_max - r_min) * rng.random() ** 1.5
        ang, dist = rng.uniform(0, 2 * np.pi), np.sqrt(rng.random()) * (radius - r)
        x, y = center + dist * np.cos(ang), center + dist * np.sin(ang)
        gx, gy = int(x // cell), int(y // cell)
        clash = False
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for ox, oy, orad in grid.get((gx + i, gy + j), ()):
                    if (ox - x) ** 2 + (oy - y) ** 2 < (orad + r + big * 0.002) ** 2:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if not clash:
            grid.setdefault((gx, gy), []).append((x, y, r))
            dots.append((x, y, r))

    paper = to_uint8(linear_to_srgb(np.array([0.86, 0.84, 0.80])))
    canvas = Image.new("RGB", (big, big), tuple(int(c) for c in paper))
    draw = ImageDraw.Draw(canvas)
    fig, bg = np.array(plate.figure_rgb), np.array(plate.background_rgb)
    for x, y, r in dots:
        inside = mask[min(big - 1, int(y)), min(big - 1, int(x))]
        base = fig if inside else bg
        jitter = rng.uniform(0.72, 1.18)
        col = to_uint8(linear_to_srgb(np.clip(base * jitter, 0, 1)))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(c) for c in col))
    small = canvas.resize((size, size), Image.Resampling.LANCZOS)
    return srgb_to_linear(to_float(np.asarray(small)))
