"""Code-owned prerequisite proofs in a closed, explicitly scoped language.

The grammar is the semantics of this synthetic probe, not an interpreter of fiction.
Every sentence must parse; callers cannot attach a model-authored semantic key to prose.
Rule scopes and observation instants are literal identifiers. No persistence is inferred.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product

VERSION = "scoped-prerequisite.v1"
SCOPES = "zero|one|two|three|four|five|six|seven|eight"
TIMES = "dawn|noon|dusk"
HATCHES = "amber|ivory"
LAMPS = "coral|azure"
_RULES = tuple(re.compile(pattern) for pattern in (
    rf"During trial (?P<scope>{SCOPES}), the (?P<hatch>{HATCHES}) hatch is open "
    rf"only while the (?P<lamp>{LAMPS}) lamp is lit\.",
    rf"Throughout trial (?P<scope>{SCOPES}), the (?P<hatch>{HATCHES}) hatch being open "
    rf"requires the (?P<lamp>{LAMPS}) lamp to be lit\.",
))
_FACTS = tuple(re.compile(pattern) for pattern in (
    rf"At (?P<time>{TIMES}) during trial (?P<scope>{SCOPES}), "
    rf"the (?P<name>{HATCHES}|{LAMPS}) (?P<kind>hatch|lamp) "
    r"was (?P<value>open|shut|lit|dark)\.",
    rf"During trial (?P<scope>{SCOPES}) at (?P<time>{TIMES}), "
    rf"the (?P<name>{HATCHES}|{LAMPS}) (?P<kind>hatch|lamp) "
    r"was (?P<value>open|shut|lit|dark)\.",
))


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class Refused(ValueError):
    """A located construction refusal; never a judgment of natural prose."""

    def __init__(self, reason: str, start: int = 0, end: int = 0):
        super().__init__(reason)
        self.reason, self.start, self.end = reason, start, end


@dataclass(frozen=True)
class Clause:
    kind: str
    scope: str
    subject: str
    start: int
    end: int
    identity: str
    moment: str = ""
    value: bool = False
    prerequisite: str = ""
    value_start: int = 0
    value_end: int = 0

    @property
    def atom(self) -> str:
        return f"{self.scope}/{self.moment}/{self.subject}"


@dataclass(frozen=True)
class Proof:
    consistent: bool
    clauses: tuple[Clause, ...]
    assignment: dict[str, bool]
    core: tuple[str, ...] = ()


def parse(text: str) -> tuple[Clause, ...]:
    """Parse every sentence; only whitespace may be skipped."""
    if not text.strip() or len(text) > 100_000:
        raise Refused("empty_or_oversized_source", 0, len(text))
    clauses = []
    position = 0
    # Scan terminators once: searching repeatedly for a whole sentence would rescan an
    # unterminated suffix at every character before refusing it.
    for terminal in re.finditer(r"[.!?]", text):
        end = terminal.end()
        raw = text[position:end]
        start = position + len(raw) - len(raw.lstrip())
        rendered = text[start:end]
        identity = digest(f"{start}:{end}:{rendered}")
        position = end
        for pattern in _RULES:
            if match := pattern.fullmatch(rendered):
                clauses.append(Clause(
                    "rule", match["scope"], "hatch." + match["hatch"], start, end, identity,
                    prerequisite="lamp." + match["lamp"],
                ))
                break
        else:
            for pattern in _FACTS:
                if match := pattern.fullmatch(rendered):
                    valid = (
                        match["kind"] == "hatch" and match["name"] in HATCHES.split("|")
                        and match["value"] in {"open", "shut"}
                    ) or (
                        match["kind"] == "lamp" and match["name"] in LAMPS.split("|")
                        and match["value"] in {"lit", "dark"}
                    )
                    if not valid:
                        raise Refused("state_outside_declared_domain", start, end)
                    clauses.append(Clause(
                        "fact", match["scope"], match["kind"] + "." + match["name"],
                        start, end, identity, moment=match["time"],
                        value=match["value"] in {"open", "lit"},
                        value_start=start + match.start("value"),
                        value_end=start + match.end("value"),
                    ))
                    break
            else:
                raise Refused("unsupported_clause", start, end)
    if text[position:].strip():
        raise Refused("unsupported_clause", position, len(text))
    if not clauses:
        raise Refused("unsupported_clause", 0, len(text))
    return tuple(clauses)


def solve(text: str) -> Proof:
    """Check facts and the necessary-condition implication open(h,t) => lit(l,t).

    An absent fact is unknown, not false. The witness assigns it as needed; all remaining
    unmentioned atoms can be false. A fact in another trial or instant does not constrain it.
    This solver never concludes that a lit lamp forces a hatch to open.
    """
    clauses = parse(text)
    facts: dict[str, Clause] = {}
    for clause in clauses:
        if clause.kind != "fact":
            continue
        if clause.atom in facts and facts[clause.atom].value != clause.value:
            return Proof(False, clauses, {}, (facts[clause.atom].identity, clause.identity))
        facts[clause.atom] = clause
    assignment = {atom: clause.value for atom, clause in facts.items()}
    for rule in (clause for clause in clauses if clause.kind == "rule"):
        for fact in facts.values():
            if fact.scope != rule.scope or fact.subject != rule.subject or not fact.value:
                continue
            required = f"{fact.scope}/{fact.moment}/{rule.prerequisite}"
            if required in facts and not facts[required].value:
                return Proof(
                    False, clauses, {}, (rule.identity, facts[required].identity, fact.identity),
                )
            assignment[required] = True
    return Proof(True, clauses, assignment)


def surface(text: str) -> dict[str, int]:
    return {
        "characters": len(text),
        "tokens": len(re.findall(r"\w+", text)),
        "sentences": len(re.findall(r"[.!?]", text)),
        "punctuation": len(re.findall(r"[^\w\s]", text)),
        "whitespace": sum(char.isspace() for char in text),
        "uppercase": sum(char.isupper() for char in text),
        "lines": text.count("\n") + 1,
    }


def token_bag(text: str) -> Counter[str]:
    return Counter(re.findall(r"\w+|[^\w\s]", text))


@dataclass(frozen=True)
class Bundle:
    original: str
    damaged: str
    control: str
    damage_edit: tuple[int, int]
    control_edit: tuple[int, int]
    contradiction: Proof
    scope: str = "zero"
    moment: str = "noon"

    @property
    def identity(self) -> str:
        return digest(f"{VERSION}:{self.scope}:{self.moment}:{self.original}")

    def verify(self) -> None:
        """Recompute the certificate; a caller-supplied key or proof is never authoritative."""
        expected = construct(self.original, scope=self.scope, moment=self.moment)
        if self != expected:
            raise Refused("certificate_does_not_reproduce_from_source")

    def manifest(self) -> dict[str, object]:
        self.verify()
        return {
            "case_id": self.identity,
            "version": VERSION,
            "source_sha256": digest(self.original),
            "variant_sha256": sorted(digest(text) for text in (
                self.original, self.damaged, self.control,
            )),
            "source_group": "one-controlled-prerequisite-family",
            "logic_certified": True,
            "certificate_scope": "closed_language_prerequisite_at_one_explicit_instant",
            "ecological_admission": False,
            "eligible_for_model_run": False,
            "production_authority": False,
            "surface_features": surface(self.damaged),
            "token_bags_equal": token_bag(self.damaged) == token_bag(self.control),
            "edit_position_decile": self.damage_edit[0] * 10 // len(self.original),
            "proof_core_size": len(self.contradiction.core),
        }


def construct(text: str, *, scope: str = "zero", moment: str = "noon") -> Bundle:
    """Make two equally sized edits; infer their roles from proofs, never supplied labels."""
    baseline = solve(text)
    if not baseline.consistent:
        raise Refused("source_already_inconsistent")
    targets = [clause for clause in baseline.clauses if (
        clause.kind == "fact" and clause.subject.startswith("hatch.")
        and clause.scope == scope and clause.moment == moment and not clause.value
    )]
    if len(targets) != 2 or len({target.subject for target in targets}) != 2:
        raise Refused("requires_two_distinct_shut_hatches_at_the_same_instant")
    edits = []
    for target in targets:
        edited = text[:target.value_start] + "open" + text[target.value_end:]
        proof = solve(edited)
        edits.append((edited, (target.value_start, target.value_end), proof))
    damaged = [item for item in edits if not item[2].consistent]
    controls = [item for item in edits if item[2].consistent]
    if len(damaged) != 1 or len(controls) != 1 or len(damaged[0][2].core) != 3:
        raise Refused("requires_one_proven_contradiction_and_one_consistent_edit")
    damage_text, damage_span, proof = damaged[0]
    control_text, control_span, _ = controls[0]
    if any(damage_text.count(damage_text[clause.start:clause.end]) != 1
           for clause in proof.clauses if clause.identity in proof.core):
        raise Refused("proof_clause_not_unique")
    # A mere lack of contradiction would allow a rule-free control. Require the control's
    # prerequisite to be observed true at exactly the same instant, not inferred by default.
    control_target = next(target for target in targets if target.value_start == control_span[0])
    control_rules = [rule for rule in baseline.clauses if (
        rule.kind == "rule" and rule.scope == scope and rule.subject == control_target.subject
    )]
    if not control_rules or any(not any(
        fact.kind == "fact" and fact.scope == scope and fact.moment == moment
        and fact.subject == rule.prerequisite and fact.value
        for fact in baseline.clauses
    ) for rule in control_rules):
        raise Refused("control_prerequisite_not_explicitly_satisfied")
    if (surface(damage_text) != surface(control_text)
            or token_bag(damage_text) != token_bag(control_text)):
        raise Refused("surface_or_token_bag_mismatch")
    if damage_span[0] * 10 // len(text) != control_span[0] * 10 // len(text):
        raise Refused("edit_position_decile_mismatch")
    return Bundle(text, damage_text, control_text, damage_span, control_span, proof, scope, moment)


def fixture(*, renderer: int = 0, swap_links: bool = False,
            reverse_rules: bool = False, reverse_facts: bool = False) -> str:
    """One synthetic family with counterbalanced names, role and sentence order."""
    if renderer not in (0, 1):
        raise ValueError("unknown renderer")
    links = [("amber", "coral"), ("ivory", "azure")]
    if swap_links:
        links = [("amber", "azure"), ("ivory", "coral")]
    if reverse_rules:
        links.reverse()
    rows = []
    # Fixed out-of-scope rules are temporal distractors, and keep the two terminal edits in
    # one position decile. This artificial layout is declared, not sold as natural prose.
    for scope in (*SCOPES.split("|")[1:], "zero"):
        for hatch, lamp in links:
            rows.append(
                f"During trial {scope}, the {hatch} hatch is open "
                f"only while the {lamp} lamp is lit."
                if renderer == 0 else
                f"Throughout trial {scope}, the {hatch} hatch being open "
                f"requires the {lamp} lamp to be lit."
            )
    facts = [("coral", "lamp", "dark"), ("azure", "lamp", "lit")]
    targets = [("amber", "hatch", "shut"), ("ivory", "hatch", "shut")]
    if reverse_facts:
        facts.reverse()
        targets.reverse()
    for name, kind, value in (*facts, *targets):
        rows.append(
            f"At noon during trial zero, the {name} {kind} was {value}."
            if renderer == 0 else
            f"During trial zero at noon, the {name} {kind} was {value}."
        )
    return "\n".join(rows)


def fixture_bundles() -> tuple[Bundle, ...]:
    return tuple(construct(fixture(
        renderer=renderer, swap_links=links, reverse_rules=rules, reverse_facts=facts,
    )) for renderer, links, rules, facts in product(
        (0, 1), (False, True), (False, True), (False, True),
    ))


def packets(bundles: tuple[Bundle, ...]) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Flat public packets; condition labels and proof spans exist only in the private key."""
    public: dict[str, dict[str, str]] = {}
    private = {}
    for bundle in bundles:
        bundle.verify()
        keys = []
        for label, text in (("intact", bundle.original), ("damaged", bundle.damaged),
                            ("control", bundle.control)):
            identity = digest(VERSION + ":packet:" + text)
            public[identity] = {"presentation_id": identity, "text": text}
            keys.append({"presentation_id": identity, "condition": label})
        private[bundle.identity] = {
            "variants": keys,
            "core": [{"start": clause.start, "end": clause.end,
                      "sha256": digest(bundle.damaged[clause.start:clause.end])}
                     for clause in bundle.contradiction.clauses
                     if clause.identity in bundle.contradiction.core],
            "certificate_scope": "closed language only; no ecological or quality label",
        }
    return [public[key] for key in sorted(public)], private
