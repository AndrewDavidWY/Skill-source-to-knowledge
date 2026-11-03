#!/usr/bin/env python3
"""Offline structural provenance checks. This does not establish truth or rights."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

KINDS = {"historical-plan", "documented-observation", "interpretation", "hypothesis", "unverified"}
ACCESS = {"synthetic", "public", "restricted"}
REUSE = {"synthetic", "public-domain", "licensed", "permission", "unknown"}
RELATIONS = {"supports", "contradicts", "context"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def valid_date(value):
    if value == "unknown":
        return True
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(data, root, public=False):
    """Return all detected errors, never mutate data or source files."""
    errors = []
    root = Path(root).resolve()
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        errors.append("schema_version must be integer 1")
    for key in ("title", "scope_note"):
        if not nonempty(data.get(key)):
            errors.append(f"{key} must be nonempty text")
    if data.get("material_mode") not in ("synthetic-demo", "research-draft"):
        errors.append("material_mode is invalid")
    if data.get("as_of") == "unknown" or not valid_date(data.get("as_of")):
        errors.append("as_of must be an ISO date")

    sources, claims = data.get("sources"), data.get("claims")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources must be a nonempty array"]
    if not isinstance(claims, list) or not claims:
        return errors + ["claims must be a nonempty array"]
    source_map, source_lines, graph, paths = {}, {}, {}, set()
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        sid = source.get("id")
        if not nonempty(sid):
            errors.append(f"{label}.id must be nonempty text")
            continue
        if sid in source_map:
            errors.append(f"duplicate source id: {sid}")
            continue
        source_map[sid] = source
        for key in ("title", "creator", "source_type", "path", "version", "rights_note", "coverage"):
            if not nonempty(source.get(key)):
                errors.append(f"{sid}.{key} must be nonempty text")
        for key in ("document_date", "event_date"):
            if not valid_date(source.get(key)):
                errors.append(f"{sid}.{key} must be an ISO date or unknown")
        access, reuse = source.get("access"), source.get("reuse_basis")
        if not isinstance(access, str) or access not in ACCESS:
            errors.append(f"{sid}.access is invalid")
        if not isinstance(reuse, str) or reuse not in REUSE:
            errors.append(f"{sid}.reuse_basis is invalid")
        if (access == "synthetic") != (reuse == "synthetic"):
            errors.append(f"{sid}: synthetic access and reuse_basis must agree")
        if data.get("material_mode") == "synthetic-demo" and access != "synthetic":
            errors.append(f"{sid}: synthetic-demo requires only synthetic sources")
        if public and (access == "restricted" or reuse == "unknown"):
            errors.append(f"{sid}: source is not eligible for a public bundle")
        old = source.get("supersedes", [])
        if not isinstance(old, list) or any(not nonempty(x) for x in old):
            errors.append(f"{sid}.supersedes must be an array of source IDs")
        else:
            graph[sid] = old
        if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            errors.append(f"{sid}.sha256 must be a lowercase SHA-256 hex digest")
        path = source.get("path")
        if not nonempty(path):
            continue
        try:
            relative = Path(path)
            resolved = (root / relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or not resolved.is_relative_to(root):
                errors.append(f"{sid}: source path must remain inside the manifest directory")
                continue
            if resolved in paths:
                errors.append(f"{sid}: path already registered; use the existing source ID")
            paths.add(resolved)
            raw = resolved.read_bytes()
            if hashlib.sha256(raw).hexdigest() != source.get("sha256"):
                errors.append(f"{sid}: source hash mismatch")
            source_lines[sid] = raw.decode("utf-8").splitlines()
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            errors.append(f"{sid}: source cannot be read as UTF-8 ({type(exc).__name__})")
    for sid, old in graph.items():
        for target in old:
            if target not in source_map:
                errors.append(f"{sid}: unknown supersedes source {target}")
    # Iterative DFS also handles large version chains without recursion overflow.
    colors = {}
    for start in graph:
        if colors.get(start):
            continue
        stack = [(start, False)]
        while stack:
            node, leaving = stack.pop()
            if leaving:
                colors[node] = 2
                continue
            if colors.get(node) == 1:
                errors.append(f"version cycle includes {node}")
                continue
            if colors.get(node) == 2:
                continue
            colors[node] = 1
            stack.append((node, True))
            stack.extend((target, False) for target in graph.get(node, []) if target in graph)

    claim_ids = set()
    for index, claim in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = claim.get("id")
        if not nonempty(cid):
            errors.append(f"{label}.id must be nonempty text")
            continue
        if cid in claim_ids:
            errors.append(f"duplicate claim id: {cid}")
        claim_ids.add(cid)
        for key in ("text", "limits"):
            if not nonempty(claim.get(key)):
                errors.append(f"{cid}.{key} must be nonempty text")
        kind = claim.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            errors.append(f"{cid}.kind is invalid")
        if claim.get("publication") not in ("ready", "hold"):
            errors.append(f"{cid}.publication must be ready or hold")
        if public and claim.get("publication") != "ready":
            errors.append(f"{cid}: claim is held from publication")
        citations = claim.get("citations")
        if not isinstance(citations, list) or not citations:
            errors.append(f"{cid}.citations must be a nonempty array")
            continue
        support = False
        for index, citation in enumerate(citations):
            clabel = f"{cid}.citations[{index}]"
            if not isinstance(citation, dict):
                errors.append(f"{clabel} must be an object")
                continue
            relation = citation.get("relation")
            if not isinstance(relation, str) or relation not in RELATIONS:
                errors.append(f"{clabel}.relation is invalid")
            support |= relation == "supports"
            sid = citation.get("source_id")
            if not isinstance(sid, str) or sid not in source_map:
                errors.append(f"{clabel}: unknown source_id")
                continue
            start, end = citation.get("start_line"), citation.get("end_line")
            if type(start) is not int or type(end) is not int or start < 1 or end < start:
                errors.append(f"{clabel}: invalid line range")
                continue
            if sid not in source_lines:
                continue
            lines = source_lines[sid]
            if end > len(lines):
                errors.append(f"{clabel}: line range exceeds source")
            elif not nonempty(citation.get("quote")) or citation["quote"] != "\n".join(lines[start - 1:end]):
                errors.append(f"{clabel}: quote does not match the complete cited lines")
        if kind in ("historical-plan", "documented-observation") and not support:
            errors.append(f"{cid}: plan or observation requires a supports citation")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--public", action="store_true", help="check declared public-bundle constraints")
    args = parser.parse_args()
    try:
        data = load_manifest(args.manifest)
        errors = validate(data, args.manifest.parent, args.public)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors = [f"manifest cannot be loaded ({type(exc).__name__})"]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(data['sources'])} sources, {len(data['claims'])} claims; structural checks only, not fact or permission approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
