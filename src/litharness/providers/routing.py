"""Model tiers per role on the one pinned provider: explicit, recorded, never a fallback (§256).

The registry serves one provider for every call, and that stays: switching between Claude and
Codex is the operator's single setting (`LITHARNESS_PROVIDER`), never an automatic reaction to
a failed call. What this adds is the model *on* that provider. A role names a capability tier
(`strong`, `standard`, `basic`) and each provider maps the tiers to its own models, so the same
routing works on a Claude-only or a Codex-only day without editing anything.

**Scene drafting stays strong.** §1a's objection to the deleted call-class routing was a book
silently written by a weaker generator; a tier is chosen per role in advance, printed by
`describe`, and recorded on every result, and the prose roles are not offered a lower tier.

**The shipped default routes nothing.** Every role resolves to `strong`, which leaves the
request's model unset so each adapter keeps its own default and existing request digests are
unchanged. `LITHARNESS_MODEL_TIERS=candidate` opts into `CANDIDATE_ROLE_TIERS`, the roles a
registered comparison is testing; an explicit `prefix=tier` list overrides both.

**An explicit request model always wins.** A call that already names its model (a registered
research arm, the reviser) is never rerouted.

`docs/model-policy.md` owns the map's review: its marker line records when it was last
reviewed against new releases and prices, and `review_status` reads it so `litharness models`
can say when the next review is due.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Final, Literal

from litharness.domain.generation import CompletionRequest

Tier = Literal["strong", "standard", "basic"]
TIERS: Final[tuple[Tier, ...]] = ("strong", "standard", "basic")

TIERS_ENV: Final = "LITHARNESS_MODEL_TIERS"
EFFORTS_ENV: Final = "LITHARNESS_CODEX_EFFORTS"

#: Each provider's model for a tier. `strong` is `None`: the adapter's own default, so a
#: routed-strong request is byte-identical to one that was never routed.
PROVIDER_TIERS: Final[dict[str, dict[Tier, str | None]]] = {
    "claude": {"strong": None, "standard": "claude-sonnet-5", "basic": "claude-haiku-4-5"},
    "codex": {"strong": None, "standard": "gpt-6-sol", "basic": "gpt-6-luna"},
}

#: Request-profile prefixes and the tier a registered comparison is testing for them. Never
#: a prose role: discovery, concept, outline and scene drafting are absent and stay strong.
CANDIDATE_ROLE_TIERS: Final[tuple[tuple[str, Tier], ...]] = (
    ("architect.", "standard"),
    ("mechanical", "basic"),
    ("title.availability.", "basic"),
)

#: Profiles that never leave the strong tier, whatever an override says: the prose, planning
#: and invention roles, and every reader instrument (a reader's model is part of what it
#: measures). An exact name, or a prefix ending in "." matched at the start of the profile.
PINNED_STRONG: Final[tuple[str, ...]] = (
    "default",
    "prose",
    "writer.discovery.",
    "writer.concept.v",
    "writer.concept.discovery.",
    "writer.concept.material.",
    "writer.overview.",
    "writer.concept.precision.",
    "writer.title.",
    "planner.",
    "reviser.",
    "tells.rewrite.",
    "revoice.",
    "director.",
    "reader.",
    "editorial.",
)


def _models_env(provider: str) -> str:
    return f"LITHARNESS_{provider.upper()}_MODELS"


def _parse_pairs(text: str, *, what: str) -> list[tuple[str, str]]:
    pairs = []
    for item in (part.strip() for part in text.split(",")):
        if not item:
            continue
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise ValueError(f"{what}: expected key=value, got {item!r}")
        pairs.append((key.strip(), value.strip()))
    return pairs


def _pinned(profile: str) -> bool:
    return any(
        profile.startswith(prefix) if prefix.endswith((".", ".v")) else profile == prefix
        for prefix in PINNED_STRONG
    )


@dataclass(frozen=True)
class ModelRouting:
    """The tier each role gets and the model each tier is on the selected provider."""

    provider: str
    role_tiers: tuple[tuple[str, Tier], ...] = ()
    models: dict[Tier, str | None] = field(default_factory=dict)

    @classmethod
    def from_environ(cls, provider: str, environ: dict[str, str] | None = None) -> ModelRouting:
        source = os.environ if environ is None else environ
        if provider not in PROVIDER_TIERS:
            raise ValueError(f"no model tiers for provider {provider!r}")
        models = dict(PROVIDER_TIERS[provider])
        name = _models_env(provider)
        for tier, model in _parse_pairs(source.get(name, ""), what=name):
            if tier not in TIERS:
                raise ValueError(f"{name}: unknown tier {tier!r}")
            models[tier] = model
        setting = source.get(TIERS_ENV, "").strip()
        if setting in {"", "off", "strong"}:
            role_tiers: tuple[tuple[str, Tier], ...] = ()
        elif setting == "candidate":
            role_tiers = CANDIDATE_ROLE_TIERS
        else:
            parsed = []
            for prefix, tier in _parse_pairs(setting, what=TIERS_ENV):
                if tier not in TIERS:
                    raise ValueError(f"{TIERS_ENV}: unknown tier {tier!r}")
                parsed.append((prefix, tier))
            role_tiers = tuple(parsed)
        return cls(provider=provider, role_tiers=role_tiers, models=models)

    def tier_for(self, profile: str) -> Tier:
        if _pinned(profile):
            return "strong"
        matches = [(prefix, tier) for prefix, tier in self.role_tiers if profile.startswith(prefix)]
        if not matches:
            return "strong"
        return max(matches, key=lambda pair: len(pair[0]))[1]

    def route(self, request: CompletionRequest) -> CompletionRequest:
        if request.model is not None:
            return request
        model = self.models.get(self.tier_for(request.profile))
        return request if model is None else replace(request, model=model)

    def describe(self, profiles: tuple[str, ...]) -> list[tuple[str, Tier, str]]:
        """Rows of (profile, tier, model) for the operator; `adapter default` for strong."""
        rows = []
        for profile in profiles:
            tier = self.tier_for(profile)
            rows.append((profile, tier, self.models.get(tier) or "adapter default"))
        return rows


def codex_efforts(environ: dict[str, str] | None = None) -> dict[str, str]:
    """`LITHARNESS_CODEX_EFFORTS` as {model: effort}, for models run at a non-default effort."""
    source = os.environ if environ is None else environ
    return dict(_parse_pairs(source.get(EFFORTS_ENV, ""), what=EFFORTS_ENV))


_POLICY_MARKER: Final = re.compile(
    r"<!--\s*model-policy:\s*last-reviewed\s+(\d{4}-\d{2}-\d{2});\s*interval-days\s+(\d+)\s*-->"
)


@dataclass(frozen=True)
class ReviewStatus:
    """When the model map was last reviewed against releases and prices, and when it is due."""

    last_reviewed: date
    interval_days: int

    @property
    def due(self) -> date:
        return self.last_reviewed + timedelta(days=self.interval_days)

    def overdue(self, today: date) -> bool:
        return today >= self.due


def review_status(policy_text: str) -> ReviewStatus | None:
    """The marker line of `docs/model-policy.md`, or None when the page carries none."""
    found = _POLICY_MARKER.search(policy_text)
    if found is None:
        return None
    return ReviewStatus(date.fromisoformat(found.group(1)), int(found.group(2)))


__all__ = [
    "CANDIDATE_ROLE_TIERS",
    "EFFORTS_ENV",
    "PINNED_STRONG",
    "PROVIDER_TIERS",
    "TIERS",
    "TIERS_ENV",
    "ModelRouting",
    "ReviewStatus",
    "Tier",
    "codex_efforts",
    "review_status",
]
