"""Everything Gemini is told. Edit the look of the artwork here; no API code lives in this
file. Changing a prompt only affects species that have no artwork in assets/art/ yet."""

POSES = [
    "perched in profile",
    "in flight with wings spread",
    "hopping on the ground, body angled toward the viewer",
    "perched and looking back over its shoulder",
    "perched with its head tilted up, singing",
    "landing with wings half open and tail fanned",
    "perched, seen from a three-quarter front angle",
]


def prompt_for(name: str) -> str:
    """The illustration prompt for one species. The pose is fixed per species name."""
    pose = POSES[sum(map(ord, name)) % len(POSES)]
    return (
        f"A single {name}, full body, {pose}, in the style of a Japanese ukiyo-e woodblock "
        "print by Hiroshige. Flat, clean areas of color with bold black keyline outlines "
        "and generous areas of plain white paper left unprinted. Ink palette strictly: "
        "red, blue, yellow, green, and black — solid flat inks, no gradients, no shading. "
        "The bird is completely isolated on a plain pure white background. "
        "No branch, no foliage, no ground, no shadow, no border, no frame, no text. "
        "The bird fills most of the square canvas and faces to the left."
    )


def plate_prompt(names: list[str]) -> str:
    """The prompt for one composed plate of several birds (used with reference images)."""
    listing = ", ".join(names)
    return (
        f"Compose a single naturalist's plate showing these {len(names)} birds together: "
        f"{listing}. Use the attached reference images for each bird's appearance and keep "
        "their style identical. Arrange them as a loose, natural flock: one bird clearly "
        "largest near the center, the others smaller at varied distances, some overlapping "
        "slightly, some perched and some in flight, facing different directions, uneven "
        "spacing like a real group of birds. Japanese ukiyo-e woodblock style: flat solid "
        "ink areas, bold black keylines, no gradients or shading. Ink palette strictly red, "
        "blue, yellow, green, black on plain white paper. Wide landscape composition with "
        "generous empty white margin on all sides. No branches, foliage, ground, shadows, "
        "border, frame, or text of any kind."
    )
