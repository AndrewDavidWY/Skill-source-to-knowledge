#!/usr/bin/env python3
"""Render a validated evidence brief to stdout; does not write or publish files."""
import argparse
import json
from pathlib import Path
import sys
from validate_evidence import load_manifest, validate

LABELS = {
    "historical-plan": "历史计划", "documented-observation": "记录中的观察",
    "interpretation": "解释／推论", "hypothesis": "待检验假设", "unverified": "未核实／有争议",
}


def plain(text):
    # Neutralize raw HTML/active links from source-derived text in generated Markdown.
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\\", "\\\\").replace("`", "\\`").replace("[", "\\[")
            .replace("]", "\\]").replace("*", "\\*").replace("_", "\\_"))


def render(data):
    lines = [f"# {plain(data['title'])}", "", f"审阅截止：{data['as_of']}", ""]
    if data["material_mode"] == "synthetic-demo":
        lines += ["**合成演练：以下人物、项目、日期和数值均为虚构，不代表真实实践或成效。**", ""]
    lines += [plain(data["scope_note"]), "", "本文件由账本生成；结构校验不替代事实、语义、权利或公开授权审阅。", ""]
    for claim in data["claims"]:
        lines += [f"## {plain(claim['id'])} · {LABELS[claim['kind']]}", "", plain(claim["text"]), "",
                  f"限制：{plain(claim['limits'])}", "", f"公开声明状态：{claim['publication']}", ""]
        for citation in claim["citations"]:
            lines += [f"- {plain(citation['source_id'])}，L{citation['start_line']}–L{citation['end_line']}，{citation['relation']}："]
            lines += [f"  > {plain(line)}" for line in citation["quote"].splitlines()]
        lines += [""]
    lines += ["## 来源与版本", ""]
    for source in data["sources"]:
        old = ", ".join(source.get("supersedes", [])) or "无"
        lines += [f"- {plain(source['id'])}：{plain(source['title'])}，版本 {plain(source['version'])}；文档日期 {source['document_date']}；事件日期 {source['event_date']}。",
                  f"  - 作者／主体：{plain(source['creator'])}；材料类型：{plain(source['source_type'])}",
                  f"  - 文件：{plain(source['path'])}；SHA-256：{source['sha256']}",
                  f"  - 可访问性：{source['access']}；再利用依据：{source['reuse_basis']}；说明：{plain(source['rights_note'])}",
                  f"  - 替代版本：{plain(old)}；读取范围：{plain(source['coverage'])}"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--public", action="store_true")
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
    print(render(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
