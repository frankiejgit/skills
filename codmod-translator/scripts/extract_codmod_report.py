#!/usr/bin/env python3
"""Extracts clean, structured Markdown from any Google Cloud codmod report.

Usage:
  python3 extract_codmod_report.py "<report_path>" --summary-only --output codmod-summary.md
  python3 extract_codmod_report.py "<report_path>" --section "Modernize to Cloud Run" --output codmod-selected-path.md
"""

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple


class SectionHTMLToMarkdownParser(HTMLParser):
    """Converts a codmod HTML section fragment into clean Markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: List[str] = []
        self.in_script = False
        self.in_style = False
        self.in_svg = False
        self.in_pre = False
        self.in_code = False
        self.in_table = False
        self.table_rows: List[List[str]] = []
        self.current_row: List[str] = []
        self.current_cell: List[str] = []
        self.in_cell = False
        self.list_stack: List[str] = []
        self.in_li = False
        self.li_has_p = False
        self.in_footnote_ref = False

    def _append(self, text: str) -> None:
        if self.in_cell:
            self.current_cell.append(text)
        else:
            self.output.append(text)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in ("script", "style", "svg"):
            setattr(self, f"in_{tag}", True)
            return
        if self.in_script or self.in_style or self.in_svg:
            return

        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "p":
            if self.in_cell:
                pass
            elif self.in_li:
                if self.li_has_p:
                    self._append(" ")
                self.li_has_p = True
            else:
                self._append("\n\n")
        elif tag == "br":
            self._append(" " if self.in_cell else "\n")
        elif tag == "sup" and "fnref:" in attr_dict.get("id", ""):
            self.in_footnote_ref = True
            self._append("[^")
        elif tag in ("strong", "b"):
            self._append("**")
        elif tag in ("em", "i"):
            self._append("*")
        elif tag == "code":
            self.in_code = True
            if not self.in_pre:
                self._append("`")
        elif tag == "pre":
            self.in_pre = True
            self._append("\n\n```\n")
        elif tag in ("ul", "ol"):
            self.list_stack.append(tag)
            if not self.in_cell:
                self._append("\n")
        elif tag == "li":
            self.in_li = True
            self.li_has_p = False
            indent = "  " * max(0, len(self.list_stack) - 1)
            fn_match = re.search(r"fn:(\d+)$", attr_dict.get("id", ""))
            if self.in_cell:
                self._append("; ")
            elif fn_match:
                self._append(f"\n{indent}- [^{fn_match.group(1)}]: ")
            else:
                self._append(f"\n{indent}- ")
        elif tag == "table":
            self.in_table = True
            self.table_rows = []
        elif tag == "tr":
            self.current_row = []
        elif tag in ("th", "td"):
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "svg"):
            setattr(self, f"in_{tag}", False)
            return
        if self.in_script or self.in_style or self.in_svg:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._append("\n")
        elif tag == "sup" and self.in_footnote_ref:
            self._append("]")
            self.in_footnote_ref = False
        elif tag in ("strong", "b"):
            self._append("**")
        elif tag in ("em", "i"):
            self._append("*")
        elif tag == "code":
            if not self.in_pre:
                self._append("`")
            self.in_code = False
        elif tag == "pre":
            self._append("\n```\n\n")
            self.in_pre = False
        elif tag == "li":
            self.in_li = False
            self.li_has_p = False
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            if not self.in_cell:
                self._append("\n")
        elif tag in ("th", "td"):
            self.in_cell = False
            cell_text = re.sub(r"\s+", " ", "".join(self.current_cell).strip()).replace("|", "\\|")
            self.current_row.append(cell_text)
        elif tag == "tr":
            if any(self.current_row):
                self.table_rows.append(self.current_row)
        elif tag == "table":
            self.in_table = False
            if self.table_rows:
                max_cols = max(len(r) for r in self.table_rows)
                self.output.append("\n\n")
                for idx, row in enumerate(self.table_rows):
                    padded = row + [""] * (max_cols - len(row))
                    self.output.append("| " + " | ".join(padded) + " |\n")
                    if idx == 0:
                        self.output.append("| " + " | ".join(["---"] * max_cols) + " |\n")
                self.output.append("\n")
            self.table_rows = []

    def handle_data(self, data: str) -> None:
        if self.in_script or self.in_style or self.in_svg:
            return
        self._append(data if self.in_pre else re.sub(r"[ \t\r\n]+", " ", data))

    def handle_entityref(self, name: str) -> None:
        if not (self.in_script or self.in_style or self.in_svg):
            self._append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if not (self.in_script or self.in_style or self.in_svg):
            self._append(html.unescape(f"&#{name};"))

    def get_markdown(self) -> str:
        text = "".join(self.output).replace("↩︎", "").replace("↩", "")
        text = re.sub(r"[ \t]+\n", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_fragment_to_markdown(fragment: str) -> str:
    parser = SectionHTMLToMarkdownParser()
    parser.feed(fragment)
    return parser.get_markdown()


def parse_subheader_metadata(raw_html: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    sub_match = re.search(
        r"<div\b[^>]*class=\"subheader\"[^>]*>(.*?)</div>\s*<div\b[^>]*class=\"main-content\"",
        raw_html,
        re.DOTALL | re.IGNORECASE,
    )
    if not sub_match:
        return metadata
    for k, v in re.findall(
        r"<div\b[^>]*class=\"subheader-key\"[^>]*>(.*?)</div>\s*<div\b[^>]*class=\"subheader-value\"[^>]*>(.*?)</div>",
        sub_match.group(1),
        re.DOTALL | re.IGNORECASE,
    ):
        metadata[html.unescape(k.strip())] = html.unescape(v.strip())
    return metadata


def parse_nav_categories(raw_html: str) -> Dict[str, List[str]]:
    categories: Dict[str, List[str]] = {}
    nav_match = re.search(r"<nav\b[^>]*>(.*?)</nav>", raw_html, re.DOTALL | re.IGNORECASE)
    if not nav_match:
        return categories
    nav_html = re.sub(r"<footer\b[^>]*>.*?</footer>", "", nav_match.group(1), flags=re.DOTALL | re.IGNORECASE)
    current_cat = "Report Sections"
    for token in re.finditer(
        r"<p\b[^>]*>(.*?)</p>|<a\b[^>]*href=\"#[^\"]+\"[^>]*>(.*?)</a>",
        nav_html,
        re.DOTALL | re.IGNORECASE,
    ):
        cat_title, link_title = token.groups()
        if cat_title is not None:
            cleaned = html.unescape(re.sub(r"<[^>]+>", "", cat_title).strip())
            if cleaned:
                current_cat = cleaned
                categories.setdefault(current_cat, [])
        elif link_title is not None:
            cleaned = html.unescape(re.sub(r"<[^>]+>", "", link_title).strip())
            if cleaned:
                categories.setdefault(current_cat, []).append(cleaned)
    return categories


def extract_sections(raw_html: str) -> List[Tuple[str, str]]:
    main_match = re.search(r"<main\b[^>]*>(.*?)</main>", raw_html, re.DOTALL | re.IGNORECASE)
    content = main_match.group(1) if main_match else raw_html
    starts = [m.start() for m in re.finditer(r"<div\b[^>]*\bclass=\"section-container\"[^>]*>", content)]
    sections: List[Tuple[str, str]] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(content)
        chunk = content[start:end]
        title_match = re.search(r"<h1[^>]*class=\"section-title\"[^>]*>(.*?)</h1>", chunk, re.DOTALL | re.IGNORECASE)
        title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1)).strip()) if title_match else f"Section {i + 1}"
        sections.append((title, chunk))
    return sections


def extract_referenced_codebase_files(sections: List[Tuple[str, str]]) -> List[str]:
    """Extracts deduplicated file paths cited in report footnotes."""
    files = set()
    for title, chunk in sections:
        if title.lower() in ("files", "classes", "further analysis"):
            continue
        for fn_match in re.finditer(
            r"<li\b[^>]*id=\"[^\"]*fn:\d+\"[^>]*>\s*<p[^>]*>(.*?)</p>",
            chunk,
            re.DOTALL | re.IGNORECASE,
        ):
            raw_text = html.unescape(re.sub(r"<[^>]+>", "", fn_match.group(1)).strip())
            candidate = re.split(r":|\s+-\s+", raw_text, maxsplit=1)[0].strip()
            if (
                candidate
                and not candidate.startswith("http")
                and ("/" in candidate or re.search(r"\.[A-Za-z0-9]{1,10}$", candidate))
                and len(candidate) < 120
            ):
                files.add(candidate)
    return sorted(files)


def summarize_files_explorer(chunk: str) -> str:
    match = re.search(r"initializeFilesExplorer\([^,]+,\s*(\{.*?\})\s*\)", chunk, re.DOTALL)
    if not match:
        return "_Files explorer data not found._"
    try:
        data = json.loads(match.group(1))
        files = [k for k in data.keys() if k]
        root_desc = html_fragment_to_markdown(data.get("", ""))
        lines = [root_desc, "", "### Scanned Project Files & Directories", ""]
        lines.extend(f"- `{f}`" for f in sorted(files))
        return "\n".join(lines)
    except Exception as exc:  # pylint: disable=broad-except
        return f"_Could not parse Files JSON: {exc}_"


def handle_markdown_report(raw: str, summary_only: bool, section_filter: Optional[str]) -> str:
    if not summary_only and not section_filter:
        return raw
    chunks = re.split(r"(?m)^(?=# )", raw)
    deferred = (
        "shift to compute engine",
        "modernize to kubernetes engine",
        "modernize to cloud run",
        "apis and endpoints",
        "security and compliance",
        "testing and quality",
        "classes",
        "further analysis",
    )
    selected = []
    for chunk in chunks:
        first_line = chunk.splitlines()[0].lower() if chunk.strip() else ""
        if section_filter and section_filter.lower() in first_line:
            selected.append(chunk)
        elif summary_only and not any(k in first_line for k in deferred):
            selected.append(chunk)
    return "\n\n".join(selected) if selected else raw


def handle_json_report(raw: str, summary_only: bool, section_filter: Optional[str]) -> str:
    try:
        data = json.loads(raw)
    except Exception:  # pylint: disable=broad-except
        return raw
    if not isinstance(data, dict):
        return raw
    lines = ["# Extracted `codmod` JSON Report", "", f"- **Top-Level Keys**: {', '.join(f'`{k}`' for k in data.keys())}\n"]
    for k, v in data.items():
        k_lower = k.lower()
        if section_filter and section_filter.lower() not in k_lower:
            continue
        if summary_only and k_lower in ("files", "classes"):
            continue
        lines.append(f"## {k}")
        lines.append(v if isinstance(v, str) else "```json\n" + json.dumps(v, indent=2)[:10000] + "\n```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract clean Markdown from any codmod report.")
    parser.add_argument("report_path", help="Path to the codmod report file")
    parser.add_argument("--summary-only", action="store_true", help="Extract overview, architecture, tech stack, and migration strategy sections")
    parser.add_argument("--section", type=str, default=None, help="Case-insensitive section name or substring to extract")
    parser.add_argument("--include-optional", action="store_true", help="Include Optional Sections (Files/Classes)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Optional file path to write extracted Markdown")
    args = parser.parse_args()

    path = Path(args.report_path).expanduser().resolve()
    if not path.exists():
        print(f"Error: Report file not found at {path}", file=sys.stderr)
        return 1

    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()

    if suffix in (".md", ".markdown"):
        final_output = handle_markdown_report(raw, args.summary_only, args.section)
    elif suffix == ".json":
        final_output = handle_json_report(raw, args.summary_only, args.section)
    else:
        metadata = parse_subheader_metadata(raw)
        categories = parse_nav_categories(raw)
        sections = extract_sections(raw)
        cited_files = extract_referenced_codebase_files(sections)

        out_lines: List[str] = [f"# Extracted `codmod` Report: `{path.name}`", ""]
        if metadata:
            out_lines.append("## Report Metadata")
            out_lines.extend(f"- **{k}**: `{v}`" for k, v in metadata.items())
            out_lines.append("")

        out_lines.append("## Report Structure & Available Sections")
        for cat, items in categories.items():
            if items:
                out_lines.append(f"- **{cat}**: {', '.join(f'`{i}`' for i in items)}")
        out_lines.append("")

        if cited_files and not args.section:
            out_lines.append("## Codebase Files Cited in Report Footnotes")
            out_lines.extend(f"- `{cf}`" for cf in cited_files)
            out_lines.append("")

        deferred_in_summary = {
            "shift to compute engine",
            "modernize to kubernetes engine",
            "modernize to cloud run",
            "apis and endpoints",
            "security and compliance",
            "testing and quality",
            "classes",
            "further analysis",
        }

        selected = []
        for title, chunk in sections:
            t_lower = title.lower()
            if args.section:
                if args.section.lower() not in t_lower:
                    continue
            elif args.summary_only:
                if t_lower in deferred_in_summary:
                    continue
            elif not args.include_optional and t_lower in ("files", "classes"):
                continue
            selected.append((title, chunk))

        if not selected:
            if args.section:
                selected = [(t, c) for t, c in sections if t.lower() in ("migration overview", "modernization opportunities", "data layer")]
            else:
                selected = [(t, c) for t, c in sections if t.lower() != "classes"]

        for title, chunk in selected:
            t_lower = title.lower()
            out_lines.append("---")
            if t_lower == "files":
                out_lines.append("# Files (Project Structure Summary)")
                out_lines.append(summarize_files_explorer(chunk))
            elif t_lower == "classes":
                out_lines.append("# Classes\n\n_(Omitted raw class graph JSON; use `--section Classes` if needed.)_")
            else:
                out_lines.append(html_fragment_to_markdown(chunk))
            out_lines.append("")

        final_output = "\n".join(out_lines)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final_output, encoding="utf-8")
        print(f"Wrote extracted Markdown ({len(final_output)} bytes) to {out_path}")
    else:
        print(final_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
