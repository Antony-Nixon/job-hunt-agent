"""Small dependency-free renderer for local draft review."""

from __future__ import annotations

import html
import re


def linkify_text(value: str) -> str:
    """Turn visible URLs into short, human-readable links after escaping text."""
    escaped = html.escape(value)
    pattern = re.compile(r"https?://[^\s<]+")

    def replace(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,);]")
        suffix = match.group(0)[len(url):]
        return f"<a href='{url}' target='_blank' rel='noopener'>Click here to open the link</a>{suffix}"

    return pattern.sub(replace, escaped)


def markdown_to_html(markdown: str, title: str = "Job Hunt Agent Draft") -> str:
    parts: list[str] = []
    in_list = False
    for line in markdown.splitlines():
        escaped = linkify_text(line)
        if in_list and not line.startswith("- "):
            parts.append("</ul>")
            in_list = False
        if line.startswith("### "):
            parts.append(f"<h3>{escaped[4:]}</h3>")
        elif line.startswith("## "):
            parts.append(f"<h2>{escaped[3:]}</h2>")
        elif line.startswith("# "):
            parts.append(f"<h1>{escaped[2:]}</h1>")
        elif line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{escaped[2:]}</li>")
        elif line.strip():
            parts.append(f"<p>{escaped}</p>")
    if in_list:
        parts.append("</ul>")
    return ("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>" + html.escape(title) + "</title>"
            "<style>body{margin:0;background:#f5f7fb;color:#172033;font:16px/1.7 Inter,system-ui,sans-serif}.document{max-width:820px;margin:40px auto;padding:42px 52px;background:#fff;border:1px solid #e5e9f0;border-radius:16px;box-shadow:0 12px 36px rgba(28,43,76,.08)}h1{font-size:30px;line-height:1.2;margin:0 0 24px;color:#172033}h2{font-size:21px;margin:30px 0 8px;color:#315efb}h3{font-size:17px;margin:24px 0 6px}p{margin:0 0 16px}ul{padding-left:24px;margin:8px 0 20px}li{margin:6px 0}@media(max-width:700px){.document{margin:0;border:0;border-radius:0;padding:28px 22px;min-height:100vh}}</style><main class='document'>" + "".join(parts) + "</main>")
