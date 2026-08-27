"""Book-cover generation and deterministic Royal Road finishing.

The image model makes artwork; this module makes the *cover*.  Keeping those jobs separate is
load-bearing: title spelling, line breaks, dimensions, and the placement of every published
word must not change because an image model sampled a different picture.  The same source art
can therefore be re-titled without buying another generation, and several art directions can
be compared under exactly the same typography. Serial-level and release-volume sets occupy
different library shelves while retaining the same canonical book and revision identity.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

COVER_WIDTH = 400
COVER_HEIGHT = 600
DEFAULT_VARIANTS = 4
MAX_VARIANTS = 8
MANIFEST_SCHEMA = "litharness.cover-set.v2"

# These are composition routes, not genres or styles.  Every one still has to be justified by
# the book description.  Their purpose is to keep a four-cover run from returning four close
# crops of the same idea while leaving the image model room to find the book's own visual hook.
VARIANT_DIRECTIONS = (
    "A character-led action image with one immediately legible physical objective.",
    "An environment-led image that makes the world's scale, danger, or impossible rule the hook.",
    "An iconic image organised around one story-specific object, power, or transformation.",
    "A relationship or confrontation image whose opposing forces are readable at thumbnail size.",
    "A high-contrast silhouette or threshold image built around a consequential choice.",
    "A close character image where an unusual ability leaves a concrete mark on the scene.",
    "A vertical journey image with distinct foreground, destination, and looming complication.",
    "A restrained mystery image that withholds the threat but shows its specific consequence.",
)


@dataclass(frozen=True, slots=True)
class CoverSpec:
    """The publication words and story context shared by every cover in a set."""

    title: str
    description: str
    author: str = "Skulitom"
    art_direction: str = ""
    book_id: str = ""
    branch_id: str = ""
    revision_id: str = ""
    #: A derived release package inside this open-ended serial. None is the serial-level cover.
    volume: int | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a cover needs a title; pass --title or a listing.json bundle")
        if not self.description.strip():
            raise ValueError(
                "Codex needs story context for cover art; pass --description, "
                "--description-file, or a listing.json bundle"
            )
        if self.volume is not None and self.volume < 1:
            raise ValueError("a cover volume must be a positive global release number")


@dataclass(frozen=True, slots=True)
class CoverSet:
    """The files produced by one completed cover run."""

    covers: tuple[Path, ...]
    manifest: Path


class CommandResult(Protocol):
    """The application-facing part of a subprocess result."""

    @property
    def returncode(self) -> int: ...

    @property
    def stdout(self) -> str: ...

    @property
    def stderr(self) -> str: ...


class Runner(Protocol):
    """An injected outer-layer process boundary."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pillow() -> tuple[Any, Any, Any, Any]:
    """Import the optional rendering dependency only when somebody asks for a cover."""
    try:
        image = importlib.import_module("PIL.Image")
        image_draw = importlib.import_module("PIL.ImageDraw")
        image_font = importlib.import_module("PIL.ImageFont")
        image_ops = importlib.import_module("PIL.ImageOps")
    except ImportError as error:  # pragma: no cover - dev and cover extras both install it
        raise ValueError(
            "cover rendering requires Pillow; install it with `uv sync --extra cover`"
        ) from error
    return image, image_draw, image_font, image_ops


def art_prompt(spec: CoverSpec, *, variant: int, target: Path, has_references: bool) -> str:
    """The exact prompt sent to a fresh Codex image-generation session."""
    if not 1 <= variant <= MAX_VARIANTS:
        raise ValueError(f"variant must be between 1 and {MAX_VARIANTS}")
    reference_rule = (
        "The attached image files are references for broad cover hierarchy or story details "
        "only. Do not reproduce their characters, wording, title treatment, or composition."
        if has_references
        else "There are no visual references; derive an original image from the story context."
    )
    extra = spec.art_direction.strip() or "No additional art direction was supplied."
    release = (
        f"volume {spec.volume} of an open-ended serial"
        if spec.volume is not None
        else "the serial as a whole"
    )
    return f"""Use the $imagegen skill to create ONE original book-cover ART image.

This is variant {variant}. Its distinct composition route is:
{VARIANT_DIRECTIONS[variant - 1]}

Book title (context only; DO NOT render it): {spec.title.strip()}
Release package: {release}
Story context:
{spec.description.strip()}

Additional art direction:
{extra}

Requirements:
- Original artwork, not an imitation of any named artist or published cover.
- 2:3 portrait canvas, preferably 1024x1536 or larger.
- One decisive, story-specific visual hook that remains legible at a 400x600 thumbnail.
- Reserve the top 30 percent as comparatively quiet title-safe space while keeping it part of
  the scene. Keep the main focal subject below that area. Leave a quieter strip at the bottom.
- Strong value separation, clear silhouette, and professional progression-fantasy cover energy
  where the story supports it; do not add generic genre objects the description does not earn.
- NO words, letters, title, author name, logo, watermark, border, mock-up, book spine, or UI.
- Generate a single cover image, not a contact sheet, collage, or set of alternatives.

{reference_rule}

Save or copy the selected full-resolution image as a PNG at exactly this path:
{target.resolve()}

Do not edit any other project file. Finish only after that exact PNG exists.
"""


def codex_argv(
    *,
    workspace: Path,
    target: Path,
    references: Sequence[Path],
    executable: str = "codex",
) -> tuple[str, ...]:
    """The non-interactive Codex command, exposed separately so the boundary is testable."""
    resolved_workspace = workspace.resolve()
    resolved_target = target.resolve()
    argv = [
        executable,
        "exec",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "-C",
        str(resolved_workspace),
    ]
    try:
        resolved_target.relative_to(resolved_workspace)
    except ValueError:
        # workspace-write permits the checkout by default. An operator may deliberately put
        # publication artifacts elsewhere, so add only that exact output directory.
        argv.extend(("--add-dir", str(resolved_target.parent)))
    for reference in references:
        argv.extend(("--image", str(reference.resolve())))
    argv.append("-")  # prompt on stdin: Windows' command-line ceiling is not a prompt ceiling
    return tuple(argv)


def generate_art(
    spec: CoverSpec,
    *,
    variant: int,
    target: Path,
    references: Sequence[Path] = (),
    workspace: Path | None = None,
    timeout: float = 900.0,
    runner: Runner | None = None,
    codex_executable: str = "codex",
) -> tuple[str, tuple[str, ...]]:
    """Ask a fresh Codex CLI session for one image and verify its promised artifact exists."""
    if timeout <= 0:
        raise ValueError("--timeout must be greater than zero")
    for reference in references:
        if not reference.is_file():
            raise ValueError(f"cover reference does not exist or is not a file: {reference}")
    target.parent.mkdir(parents=True, exist_ok=True)
    prompt = art_prompt(spec, variant=variant, target=target, has_references=bool(references))
    working = (workspace or Path.cwd()).resolve()
    argv = codex_argv(
        workspace=working,
        target=target,
        references=references,
        executable=codex_executable,
    )
    if runner is None:
        raise ValueError("Codex generation requires an injected command runner")
    result = runner(argv, timeout=timeout, cwd=str(working), stdin=prompt)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        if len(detail) > 2000:
            detail = detail[-2000:]
        raise ValueError(
            f"Codex cover-art generation failed with exit {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    if not target.is_file():
        raise ValueError(
            "Codex reported success but did not create the requested art file: " f"{target}"
        )
    return prompt, argv


def _font(image_font: Any, size: int, requested: Path | None) -> tuple[Any, str]:
    if requested is not None:
        if not requested.is_file():
            raise ValueError(f"font does not exist or is not a file: {requested}")
        return image_font.truetype(str(requested), size=size), str(requested.resolve())

    candidates = (
        "DejaVuSansCondensed-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/bahnschrift.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    )
    for candidate in candidates:
        try:
            return image_font.truetype(candidate, size=size), candidate
        except OSError:
            continue
    # Pillow 10.1+ accepts a size here. Both supported extras resolve Pillow >=11.
    return image_font.load_default(size=size), "Pillow default"


def _wrap(draw: Any, text: str, font: Any, max_width: int) -> tuple[str, ...]:
    words = text.split()
    if not words:
        return ()
    lines: list[str] = []
    current = words[0]
    if draw.textbbox((0, 0), current, font=font)[2] > max_width:
        return ()
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if draw.textbbox((0, 0), current, font=font)[2] > max_width:
                return ()
    lines.append(current)
    return tuple(lines)


def _title_layout(
    draw: Any, image_font: Any, title: str, font_path: Path | None
) -> tuple[Any, str, str, int]:
    for size in range(62, 21, -2):
        font, resolved = _font(image_font, size, font_path)
        lines = _wrap(draw, title.strip(), font, COVER_WIDTH - 44)
        if not lines or len(lines) > 4:
            continue
        spacing = max(4, size // 9)
        rendered = "\n".join(lines)
        bounds = draw.multiline_textbbox(
            (0, 0), rendered, font=font, spacing=spacing, align="center", stroke_width=2
        )
        if bounds[3] - bounds[1] <= 190:
            return font, resolved, rendered, spacing
    raise ValueError(
        "the title cannot fit legibly in four lines at 400x600; shorten it or provide a "
        "condensed font with --font"
    )


def _normalise_art(source: Path, destination: Path) -> None:
    Image, _ImageDraw, _ImageFont, ImageOps = _pillow()
    if not source.is_file():
        raise ValueError(f"cover art does not exist or is not a file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    with Image.open(source) as opened:
        normalised = ImageOps.exif_transpose(opened).convert("RGB")
        normalised.save(temporary, format="PNG")
    temporary.replace(destination)


def compose_cover(
    art: Path, output: Path, spec: CoverSpec, *, font_path: Path | None = None
) -> str:
    """Put publication words over art and return the font recorded in provenance."""
    Image, ImageDraw, ImageFont, ImageOps = _pillow()
    if not art.is_file():
        raise ValueError(f"cover art does not exist or is not a file: {art}")
    with Image.open(art) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        cover = ImageOps.fit(
            source,
            (COVER_WIDTH, COVER_HEIGHT),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        ).convert("RGBA")

    shade = Image.new("RGBA", cover.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    for y in range(220):
        alpha = max(0, round(178 * (1 - y / 220) ** 1.7))
        shade_draw.line((0, y, COVER_WIDTH, y), fill=(5, 8, 18, alpha))
    if spec.author.strip():
        for y in range(490, COVER_HEIGHT):
            alpha = round(145 * ((y - 490) / (COVER_HEIGHT - 490)) ** 1.5)
            shade_draw.line((0, y, COVER_WIDTH, y), fill=(5, 8, 18, alpha))
    cover = Image.alpha_composite(cover, shade)
    draw = ImageDraw.Draw(cover)

    title_font, resolved_font, rendered_title, spacing = _title_layout(
        draw, ImageFont, spec.title, font_path
    )
    title_box = draw.multiline_textbbox(
        (0, 0),
        rendered_title,
        font=title_font,
        spacing=spacing,
        align="center",
        stroke_width=2,
    )
    title_height = title_box[3] - title_box[1]
    draw.multiline_text(
        (COVER_WIDTH / 2, 24 + title_height / 2),
        rendered_title,
        font=title_font,
        fill=(248, 244, 228, 255),
        anchor="mm",
        align="center",
        spacing=spacing,
        stroke_width=2,
        stroke_fill=(12, 13, 20, 235),
    )

    if spec.author.strip():
        author_font, _ = _font(ImageFont, 25, font_path)
        author = " ".join(spec.author.strip().split())
        author_box = draw.textbbox((0, 0), author, font=author_font, stroke_width=1)
        if author_box[2] - author_box[0] > COVER_WIDTH - 44:
            author_font, _ = _font(ImageFont, 19, font_path)
            author_box = draw.textbbox((0, 0), author, font=author_font, stroke_width=1)
        if author_box[2] - author_box[0] > COVER_WIDTH - 44:
            raise ValueError("the author name does not fit at 400x600; use a shorter display name")
        draw.text(
            (COVER_WIDTH / 2, COVER_HEIGHT - 26),
            author,
            font=author_font,
            fill=(248, 244, 228, 255),
            anchor="mm",
            stroke_width=1,
            stroke_fill=(12, 13, 20, 235),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    cover.convert("RGB").save(temporary, format="PNG", optimize=True)
    temporary.replace(output)
    with Image.open(output) as verification:
        if verification.size != (COVER_WIDTH, COVER_HEIGHT):
            raise ValueError(
                f"cover export is {verification.width}x{verification.height}, expected "
                f"{COVER_WIDTH}x{COVER_HEIGHT}"
            )
    return resolved_font


def create_cover_set(
    output_dir: Path,
    spec: CoverSpec,
    *,
    variants: int = DEFAULT_VARIANTS,
    supplied_art: Sequence[Path] = (),
    references: Sequence[Path] = (),
    font_path: Path | None = None,
    timeout: float = 900.0,
    force: bool = False,
    workspace: Path | None = None,
    generated_at: str = "",
    runner: Runner | None = None,
    codex_executable: str = "codex",
) -> CoverSet:
    """Generate or import several art routes, finish them alike, and write one manifest."""
    count = len(supplied_art) if supplied_art else variants
    if not 1 <= count <= MAX_VARIANTS:
        raise ValueError(f"cover variants must be between 1 and {MAX_VARIANTS}")
    if supplied_art and references:
        raise ValueError("--reference only affects generation and cannot be used with --art")

    output_dir = output_dir.resolve()
    manifest_path = output_dir / "cover-manifest.json"
    targets = [manifest_path]
    for index in range(1, count + 1):
        targets.extend(
            (output_dir / f"cover-{index:02d}.art.png", output_dir / f"cover-{index:02d}.png")
        )
    collisions = [target for target in targets if target.exists()]
    if collisions and not force:
        names = ", ".join(path.name for path in collisions)
        raise FileExistsError(f"cover output already exists ({names}); pass --force to replace it")
    output_dir.mkdir(parents=True, exist_ok=True)
    if force:
        # A failed replacement may leave a partial set, but it must never leave the *old*
        # manifest claiming that newly replaced files are its own. The explicit flag authorises
        # removing this exact derived artifact; source art supplied by the operator is untouched.
        manifest_path.unlink(missing_ok=True)

    rows: list[dict[str, Any]] = []
    covers: list[Path] = []
    for index in range(1, count + 1):
        art_target = output_dir / f"cover-{index:02d}.art.png"
        cover_target = output_dir / f"cover-{index:02d}.png"
        command: tuple[str, ...] = ()
        prompt = ""
        if supplied_art:
            _normalise_art(supplied_art[index - 1], art_target)
            source_kind = "supplied"
        else:
            if force:
                # Success means this invocation made this artifact. Without removing the prior
                # derived image first, an agent that returned zero but failed to save could make
                # the existence check accept yesterday's art as today's generation.
                art_target.unlink(missing_ok=True)
            prompt, command = generate_art(
                spec,
                variant=index,
                target=art_target,
                references=references,
                workspace=workspace,
                timeout=timeout,
                runner=runner,
                codex_executable=codex_executable,
            )
            source_kind = "codex-cli-imagegen"
        resolved_font = compose_cover(art_target, cover_target, spec, font_path=font_path)
        covers.append(cover_target)
        rows.append(
            {
                "variant": index,
                "direction": VARIANT_DIRECTIONS[index - 1],
                "source": source_kind,
                "art": art_target.name,
                "cover": cover_target.name,
                "art_sha256": _sha256(art_target),
                "cover_sha256": _sha256(cover_target),
                "font": resolved_font,
                "prompt": prompt or None,
                "command": list(command) or None,
            }
        )

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": generated_at or None,
        "book": (
            {
                "book_id": spec.book_id,
                "branch_id": spec.branch_id,
                "revision_id": spec.revision_id,
            }
            if spec.book_id
            else None
        ),
        "release": (
            {"kind": "volume", "number": spec.volume}
            if spec.volume is not None
            else {"kind": "serial"}
        ),
        "title": spec.title.strip(),
        "author": spec.author.strip() or None,
        "description": spec.description.strip(),
        "art_direction": spec.art_direction.strip() or None,
        "dimensions": {"width": COVER_WIDTH, "height": COVER_HEIGHT},
        "references": [
            {"path": str(path.resolve()), "sha256": _sha256(path)} for path in references
        ],
        "variants": rows,
    }
    temporary_manifest = manifest_path.with_name(
        f".{manifest_path.name}.{uuid.uuid4().hex}.tmp"
    )
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_manifest.replace(manifest_path)
    return CoverSet(covers=tuple(covers), manifest=manifest_path)
