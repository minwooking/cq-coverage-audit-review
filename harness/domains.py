"""Domain parameters for the holdout harness (Brick, IOF Core, ...).

One TOML file per domain in ``paper/access2026/domains/``. This module only loads and
validates them; it never reads a snapshot, bank, or network. The Brick file carries
exactly the values that used to be hard-coded, so Brick behaviour is unchanged.

A domain whose bank is not frozen has ``bank.sha256`` unset. Anything that scores
(``require_frozen_bank``) refuses such a domain.

CLI (used by variants/build_domain.sh):
    python domains.py get <domain> <dotted.key>     # print one value
    python domains.py show <domain>                 # print the whole config as JSON
"""
from __future__ import annotations

import json
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
REPO = ACCESS.parent.parent
DOMAINS_DIR = ACCESS / "domains"
DEFAULT_DOMAIN = "brick"


class DomainError(SystemExit):
    """Refusal that reads like the harness's other REFUSING TO RUN messages."""


@dataclass(frozen=True)
class DomainConfig:
    name: str
    title: str
    cluster_prefix: str
    cq_id_prefix: str
    snapshot_path: Path
    snapshot_sha256: str
    snapshot_format: str
    namespaces: tuple[tuple[str, str], ...]
    corpus_builder: str
    corpus_path: Path
    corpus_generated_from: str
    bank_path: Path
    bank_sha256: str | None
    bank_rows: int | None
    paraphrases_path: Path | None
    variants_dir: Path
    variants_work_dir: Path
    variants_manifest: Path
    cq_json: Path  # relative to REPO
    documented_exclusions: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    # PREREG.md addendum 15 §15.2 per-domain eligibility policy: with True, a
    # primary cell whose only preflight failure is the mechanical grounding-
    # absence category is recorded as an exclusion instead of refusing the run.
    # Unset (brick) = False = the strict, pre-addendum behaviour, unchanged.
    auto_exclude_grounding_ineligible: bool = False
    # PREREG.md addendum 15 §15.7-2/4: the committed eligibility-preflight
    # manifest that registers this domain's analysis design (eligible CQ x variant
    # grid, exclusion rule, m, N). Unset = the domain has no registered analysis
    # design beyond analyze_holdout's Brick-only REGISTERED_* tables.
    preflight_manifest: Path | None = None

    @property
    def bank_frozen(self) -> bool:
        return self.bank_sha256 is not None and self.bank_rows is not None

    def require_frozen_bank(self) -> None:
        if not self.bank_frozen:
            raise DomainError(
                f"REFUSING TO RUN: the CQ bank of domain {self.name!r} is not frozen "
                f"(bank.sha256/bank.rows unset in domains/{self.name}.toml). "
                "Scoring and analysis need a frozen, registered bank."
            )

    def qualify_cluster(self, cluster_id: str) -> str:
        """Domain-qualified cluster id, e.g. ``iof:CQI01``; never collides across domains."""
        return f"{self.cluster_prefix}:{cluster_id}"

    def qname(self, iri) -> str:
        s = str(iri)
        for prefix, ns in self.namespaces:
            if s.startswith(ns):
                return prefix + s[len(ns):]
        return s


def _p(value: str | None) -> Path | None:
    return None if value is None else ACCESS / value


def load_domain(name: str, directory: Path = DOMAINS_DIR) -> DomainConfig:
    path = directory / f"{name}.toml"
    if not path.is_file():
        known = sorted(p.stem for p in directory.glob("*.toml"))
        raise DomainError(f"unknown domain {name!r}; known: {known}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        snap, corpus, bank, var = raw["snapshot"], raw["corpus"], raw["bank"], raw["variants"]
        cfg = DomainConfig(
            name=raw["name"],
            title=raw["title"],
            cluster_prefix=raw["cluster_prefix"],
            cq_id_prefix=raw["cq_id_prefix"],
            snapshot_path=ACCESS / snap["path"],
            snapshot_sha256=snap["sha256"],
            snapshot_format=snap["format"],
            namespaces=tuple(raw["namespaces"].items()),
            corpus_builder=corpus["builder"],
            corpus_path=ACCESS / corpus["path"],
            corpus_generated_from=corpus["generated_from"],
            bank_path=ACCESS / bank["path"],
            bank_sha256=bank.get("sha256"),
            bank_rows=bank.get("rows"),
            paraphrases_path=_p(bank.get("paraphrases")),
            variants_dir=ACCESS / var["dir"],
            variants_work_dir=ACCESS / var["work_dir"],
            variants_manifest=ACCESS / var["manifest"],
            cq_json=Path(var["cq_json"]),
            documented_exclusions=tuple(
                (e["variant"], e["cq_id"], e["reason"]) for e in raw.get("documented_exclusions", [])),
            auto_exclude_grounding_ineligible=bool(
                raw.get("eligibility", {}).get("auto_exclude_grounding_ineligible", False)),
            preflight_manifest=_p(raw.get("analysis", {}).get("preflight_manifest")),
        )
    except KeyError as exc:
        raise DomainError(f"domains/{name}.toml is missing required key {exc}") from exc
    if cfg.name != name:
        raise DomainError(f"domains/{name}.toml declares name {cfg.name!r}")
    if (cfg.bank_sha256 is None) != (cfg.bank_rows is None):
        raise DomainError(f"domains/{name}.toml: bank.sha256 and bank.rows must be set together")
    return cfg


def known_domains(directory: Path = DOMAINS_DIR) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.toml"))


def _dotted(cfg: DomainConfig, key: str):
    # Paths print relative to the repo root so shell scripts can use them after `cd $REPO`.
    mapping = {
        "name": cfg.name,
        "cq_id_prefix": cfg.cq_id_prefix,
        "cluster_prefix": cfg.cluster_prefix,
        "snapshot.path": cfg.snapshot_path,
        "corpus.path": cfg.corpus_path,
        "corpus.builder": cfg.corpus_builder,
        "variants.dir": cfg.variants_dir,
        "variants.work_dir": cfg.variants_work_dir,
        "variants.manifest": cfg.variants_manifest,
        "variants.cq_json": cfg.cq_json,
        "bank.path": cfg.bank_path,
        "bank.frozen": str(cfg.bank_frozen).lower(),
    }
    if key not in mapping:
        raise DomainError(f"unknown key {key!r}; known: {sorted(mapping)}")
    value = mapping[key]
    if isinstance(value, Path) and value.is_absolute():
        try:
            return value.relative_to(REPO)
        except ValueError:
            return value
    return value


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "get":
        print(_dotted(load_domain(argv[1]), argv[2]))
        return 0
    if len(argv) == 2 and argv[0] == "show":
        cfg = load_domain(argv[1])
        print(json.dumps({k: str(v) for k, v in cfg.__dict__.items()}, indent=2, ensure_ascii=False))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
