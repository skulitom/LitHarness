from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest
from PIL import Image

from litharness.application import covers
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.providers.cli import CommandResult


def art(path: Path, colour: tuple[int, int, int] = (65, 105, 160)) -> Path:
    Image.new("RGB", (800, 1200), colour).save(path)
    return path


def spec(**changes: str) -> covers.CoverSpec:
    values = {
        "title": "The Cinder Road",
        "description": "A debtor walks a road that charges memories instead of coin.",
        "author": "A. Writer",
        "art_direction": "Ember orange against midnight blue.",
    }
    values.update(changes)
    return covers.CoverSpec(**values)


def test_a_cover_needs_publication_words_and_story_context() -> None:
    assert covers.CoverSpec(title="A Title", description="A story.").author == "Skulitom"
    with pytest.raises(ValueError, match="needs a title"):
        spec(title=" ")
    with pytest.raises(ValueError, match="story context"):
        spec(description=" ")
    with pytest.raises(ValueError, match="positive global release number"):
        covers.CoverSpec(title="A Title", description="A story.", volume=0)


def test_the_image_prompt_reserves_typography_space_but_forbids_generated_words(
    tmp_path: Path,
) -> None:
    prompt = covers.art_prompt(spec(), variant=2, target=tmp_path / "art.png", has_references=True)
    assert "$imagegen" in prompt
    assert "2:3 portrait" in prompt
    assert "top 30 percent" in prompt
    assert "DO NOT render it" in prompt
    assert "NO words" in prompt
    assert covers.VARIANT_DIRECTIONS[1] in prompt
    assert "references for broad cover hierarchy" in prompt
    volume_prompt = covers.art_prompt(
        covers.CoverSpec(title="A Title", description="A story.", volume=3),
        variant=1,
        target=tmp_path / "volume-art.png",
        has_references=False,
    )
    assert "volume 3 of an open-ended serial" in volume_prompt
    with pytest.raises(ValueError, match="variant"):
        covers.art_prompt(spec(), variant=0, target=tmp_path / "art.png", has_references=False)


def test_the_codex_command_is_ephemeral_sandboxed_and_accepts_references(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    target = tmp_path / "publication" / "art.png"
    reference = tmp_path / "reference.png"
    argv = covers.codex_argv(
        workspace=workspace,
        target=target,
        references=(reference,),
        executable="codex.cmd",
    )
    assert argv[:2] == ("codex.cmd", "exec")
    assert "--ephemeral" in argv
    assert argv[3:5] == ("--sandbox", "workspace-write")
    assert "--add-dir" in argv
    assert "--image" in argv
    assert argv[-1] == "-"

    inside = workspace / "covers" / "art.png"
    assert "--add-dir" not in covers.codex_argv(
        workspace=workspace, target=inside, references=()
    )


def test_the_scratch_workspace_tells_codex_its_absent_repository_is_deliberate(
    tmp_path: Path,
) -> None:
    """`generate_art` runs Codex in a temporary directory to keep AGENTS.md out of the call.

    A fresh temporary directory is never a trusted project and is never a git repository, so
    without this flag Codex refuses every cover generation before drawing anything — which is
    what it did from 2026-08-28 10:12 until the flag landed.
    """
    argv = covers.codex_argv(
        workspace=tmp_path, target=tmp_path / "art.png", references=()
    )
    assert "--skip-git-repo-check" in argv
    assert argv.index("--skip-git-repo-check") < argv.index("-C")


def test_codex_generation_sends_the_prompt_on_stdin_and_requires_the_artifact(
    tmp_path: Path,
) -> None:
    target = tmp_path / "art.png"
    seen: dict[str, object] = {}

    def runner(
        argv: Sequence[str], *, timeout: float, cwd: str | None = None, stdin: str | None = None
    ) -> CommandResult:
        seen.update(argv=tuple(argv), timeout=timeout, cwd=cwd, stdin=stdin)
        art(target)
        return CommandResult(0, "done")

    prompt, argv = covers.generate_art(
        spec(), variant=1, target=target, workspace=tmp_path, timeout=12, runner=runner
    )
    assert target.is_file()
    assert seen == {"argv": argv, "timeout": 12, "cwd": str(tmp_path), "stdin": prompt}

    def no_file(
        _argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult:
        return CommandResult(0, "claimed success")

    with pytest.raises(ValueError, match="did not create"):
        covers.generate_art(
            spec(), variant=1, target=tmp_path / "missing.png", runner=no_file
        )


def test_generation_refuses_bad_inputs_and_surfaces_codex_failure(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        covers.generate_art(spec(), variant=1, target=tmp_path / "x.png", timeout=0)
    with pytest.raises(ValueError, match="reference does not exist"):
        covers.generate_art(
            spec(),
            variant=1,
            target=tmp_path / "x.png",
            references=(tmp_path / "missing-reference.png",),
        )
    with pytest.raises(ValueError, match="injected command runner"):
        covers.generate_art(spec(), variant=1, target=tmp_path / "x.png")

    def failed(
        _argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult:
        return CommandResult(7, "", "image service unavailable")

    with pytest.raises(ValueError, match=r"exit 7.*image service unavailable"):
        covers.generate_art(spec(), variant=1, target=tmp_path / "x.png", runner=failed)


def test_composition_draws_exact_publication_dimensions_and_text(tmp_path: Path) -> None:
    source = art(tmp_path / "source.png")
    output = tmp_path / "cover.png"
    font = covers.compose_cover(source, output, spec())
    assert font
    with Image.open(output) as rendered:
        assert rendered.size == (400, 600)
        assert rendered.mode == "RGB"
        assert rendered.getpixel((200, 30)) != (65, 105, 160)


def test_composition_refuses_words_that_cannot_be_legible(tmp_path: Path) -> None:
    source = art(tmp_path / "source.png")
    with pytest.raises(ValueError, match="title cannot fit"):
        covers.compose_cover(source, tmp_path / "cover.png", spec(title="W" * 100))
    with pytest.raises(ValueError, match="author name does not fit"):
        covers.compose_cover(
            source,
            tmp_path / "cover.png",
            spec(author="IMPOSSIBLYLONGDISPLAYNAME" * 8),
        )
    with pytest.raises(ValueError, match="font does not exist"):
        covers.compose_cover(
            source, tmp_path / "cover.png", spec(), font_path=tmp_path / "absent.ttf"
        )
    with pytest.raises(ValueError, match="cover art does not exist"):
        covers.compose_cover(tmp_path / "absent.png", tmp_path / "cover.png", spec())


def test_a_supplied_art_set_is_self_contained_versioned_and_collision_safe(
    tmp_path: Path,
) -> None:
    source_a = art(tmp_path / "a.png", (20, 40, 80))
    source_b = art(tmp_path / "b.png", (100, 50, 20))
    output = tmp_path / "covers"
    result = covers.create_cover_set(
        output,
        spec(book_id="book-1", branch_id="branch-1", revision_id="revision-1"),
        supplied_art=(source_a, source_b),
        generated_at="2026-08-26T12:00:00Z",
    )
    assert [path.name for path in result.covers] == ["cover-01.png", "cover-02.png"]
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["schema"] == covers.MANIFEST_SCHEMA
    assert manifest["dimensions"] == {"width": 400, "height": 600}
    assert manifest["generated_at"] == "2026-08-26T12:00:00Z"
    assert manifest["book"] == {
        "book_id": "book-1",
        "branch_id": "branch-1",
        "revision_id": "revision-1",
    }
    assert manifest["release"] == {"kind": "serial"}
    assert [row["source"] for row in manifest["variants"]] == ["supplied", "supplied"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", row["cover_sha256"]) for row in manifest["variants"])
    with pytest.raises(FileExistsError, match="--force"):
        covers.create_cover_set(output, spec(), supplied_art=(source_a, source_b))
    assert covers.create_cover_set(
        output, spec(), supplied_art=(source_a, source_b), force=True
    ).manifest.is_file()


def test_a_generated_set_uses_one_fresh_codex_call_per_variant(tmp_path: Path) -> None:
    prompts: list[str] = []
    workspaces: list[str | None] = []

    def runner(
        _argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult:
        assert stdin is not None
        prompts.append(stdin)
        workspaces.append(cwd)
        match = re.search(r"exactly this path:\n(.+)\n", stdin)
        assert match is not None
        art(Path(match.group(1)))
        return CommandResult(0, "done")

    output = tmp_path / "generated"
    result = covers.create_cover_set(output, spec(), variants=2, runner=runner)
    assert len(result.covers) == 2
    assert len(prompts) == 2
    assert len(set(workspaces)) == 2
    assert all(Path(value).name.startswith("litharness-cover-") for value in workspaces if value)
    assert all(not Path(value).exists() for value in workspaces if value)
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert [row["source"] for row in manifest["variants"]] == [
        "codex-cli-imagegen",
        "codex-cli-imagegen",
    ]
    assert manifest["variants"][0]["prompt"] != manifest["variants"][1]["prompt"]


def test_a_failed_forced_generation_cannot_inherit_old_art_or_its_manifest(
    tmp_path: Path,
) -> None:
    source = art(tmp_path / "old.png")
    output = tmp_path / "covers"
    covers.create_cover_set(output, spec(), supplied_art=(source,))

    def no_file(
        _argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult:
        return CommandResult(0, "claimed success")

    with pytest.raises(ValueError, match="did not create"):
        covers.create_cover_set(output, spec(), variants=1, force=True, runner=no_file)
    assert not (output / "cover-01.art.png").exists()
    assert not (output / "cover-manifest.json").exists()


def test_cover_set_bounds_and_generation_only_references(tmp_path: Path) -> None:
    source = art(tmp_path / "source.png")
    with pytest.raises(ValueError, match="between 1 and"):
        covers.create_cover_set(tmp_path / "none", spec(), variants=0)
    with pytest.raises(ValueError, match="cannot be used with --art"):
        covers.create_cover_set(
            tmp_path / "bad",
            spec(),
            supplied_art=(source,),
            references=(source,),
        )


def test_the_cli_reads_the_listing_bundle_without_retyping_and_never_calls_codex(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "listing.json"
    bundle.write_text(
        json.dumps({"title": "Memory Toll", "listing": "A road takes memories as payment."}),
        encoding="utf-8",
    )
    source_a = art(tmp_path / "a.png")
    source_b = art(tmp_path / "b.png")
    output = tmp_path / "finished"
    assert (
        main(
            [
                "cover",
                "--out",
                str(output),
                "--bundle",
                str(bundle),
                "--author",
                "A. Writer",
                "--art",
                str(source_a),
                "--art",
                str(source_b),
            ]
        )
        == EXIT_OK
    )
    printed = capsys.readouterr().out
    assert "cover-01.png" in printed
    manifest = json.loads((output / "cover-manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "Memory Toll"
    assert manifest["description"] == "A road takes memories as payment."
    assert all(row["command"] is None for row in manifest["variants"])


def test_an_existing_book_defaults_to_its_library_shelf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "book.db"
    assert main(["--database", str(database), "init"]) == EXIT_OK
    assert (
        main(
            [
                "--database",
                str(database),
                "new",
                "Memory Toll",
                "--premise",
                "A road takes one memory at every gate.",
                "--scenes",
                "6",
            ]
        )
        == EXIT_OK
    )
    capsys.readouterr()
    source = art(tmp_path / "art.png")
    assert (
        main(["--database", str(database), "cover", "--art", str(source)])
        == EXIT_OK
    )
    shelf = tmp_path / "book-library" / "memory-toll" / "covers"
    manifest = json.loads((shelf / "cover-manifest.json").read_text(encoding="utf-8"))
    assert (shelf / "cover-01.png").is_file()
    assert manifest["title"] == "Memory Toll"
    assert manifest["description"] == "A road takes one memory at every gate."
    assert manifest["author"] == "Skulitom"
    assert manifest["book"]["book_id"]
    assert manifest["book"]["revision_id"]

    assert (
        main(
            [
                "--database",
                str(database),
                "cover",
                "--volume",
                "1",
                "--art",
                str(source),
            ]
        )
        == EXIT_OK
    )
    volume_shelf = (
        tmp_path / "book-library" / "memory-toll" / "volumes" / "Volume1" / "covers"
    )
    volume_manifest = json.loads(
        (volume_shelf / "cover-manifest.json").read_text(encoding="utf-8")
    )
    assert (volume_shelf / "cover-01.png").is_file()
    assert volume_manifest["release"] == {"kind": "volume", "number": 1}
    assert volume_manifest["book"] == manifest["book"], (
        "release packaging must not mint another book or revision identity"
    )


def test_the_cli_reports_a_non_object_bundle_as_an_operational_fault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "listing.json"
    bundle.write_text("[]", encoding="utf-8")
    assert main(["cover", "--out", str(tmp_path / "covers"), "--bundle", str(bundle)]) == EXIT_FAULT
    assert "must be a JSON object" in capsys.readouterr().err
