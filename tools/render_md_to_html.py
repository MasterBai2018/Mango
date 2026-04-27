#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 Markdown 文档转换为风格严肃的 HTML 文档。

默认输入: doc/Mango_测试使用说明.md
默认输出: doc/Mango_测试使用说明.html
"""

from __future__ import annotations

from pathlib import Path
import html
import re
import sys


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def inline_format(text: str) -> str:
    """处理行内代码和粗体等常见语法。"""
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def close_lists(out: list[str], list_stack: list[str]) -> None:
    while list_stack:
        out.append(f"</{list_stack.pop()}>")


def make_anchor_id(text: str, used_ids: dict[str, int], fallback_index: int) -> str:
    """生成稳定锚点ID，支持中文标题。"""
    base = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", text).strip().replace(" ", "-").lower()
    if not base:
        base = f"section-{fallback_index}"
    count = used_ids.get(base, 0)
    used_ids[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def render_markdown(md_text: str, title: str) -> str:
    lines = md_text.splitlines()
    out: list[str] = []
    list_stack: list[str] = []
    in_code = False
    in_table = False
    table_header_done = False
    in_blockquote = False
    headings: list[tuple[int, str, str]] = []
    used_ids: dict[str, int] = {}
    heading_index = 1

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False
            close_lists(out, list_stack)
            if in_blockquote:
                out.append("</blockquote>")
                in_blockquote = False
            if not in_code:
                in_code = True
                out.append("<pre><code>")
            else:
                in_code = False
                out.append("</code></pre>")
            i += 1
            continue

        if in_code:
            out.append(escape(line))
            i += 1
            continue

        # 空行
        if not stripped:
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False
            close_lists(out, list_stack)
            if in_blockquote:
                out.append("</blockquote>")
                in_blockquote = False
            i += 1
            continue

        # 分割线
        if stripped in {"---", "***"}:
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False
            close_lists(out, list_stack)
            if in_blockquote:
                out.append("</blockquote>")
                in_blockquote = False
            out.append("<hr />")
            i += 1
            continue

        # 标题
        m_heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m_heading:
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False
            close_lists(out, list_stack)
            if in_blockquote:
                out.append("</blockquote>")
                in_blockquote = False
            level = len(m_heading.group(1))
            raw_heading = m_heading.group(2).strip()
            content = inline_format(raw_heading)
            anchor_id = make_anchor_id(raw_heading, used_ids, heading_index)
            heading_index += 1
            headings.append((level, raw_heading, anchor_id))
            out.append(f'<h{level} id="{anchor_id}">{content}</h{level}>')
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False
            close_lists(out, list_stack)
            content = stripped[1:].lstrip()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{inline_format(content)}</p>")
            i += 1
            continue
        else:
            if in_blockquote:
                out.append("</blockquote>")
                in_blockquote = False

        # 表格
        if "|" in line and line.lstrip().startswith("|"):
            # 判断是否表头分隔线
            if re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", line):
                i += 1
                continue

            if not in_table:
                close_lists(out, list_stack)
                out.append('<table><tbody>')
                in_table = True
                table_header_done = False

            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            tag = "th" if not table_header_done else "td"
            out.append("<tr>" + "".join(f"<{tag}>{inline_format(c)}</{tag}>" for c in cells) + "</tr>")
            if not table_header_done:
                table_header_done = True
            i += 1
            continue
        else:
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                table_header_done = False

        # 无序列表
        m_ul = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m_ul:
            indent = len(m_ul.group(1)) // 2
            content = m_ul.group(2)
            while len(list_stack) > indent:
                out.append(f"</{list_stack.pop()}>")
            while len(list_stack) < indent + 1:
                out.append("<ul>")
                list_stack.append("ul")
            out.append(f"<li>{inline_format(content)}</li>")
            i += 1
            continue

        # 有序列表
        m_ol = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m_ol:
            indent = len(m_ol.group(1)) // 2
            content = m_ol.group(2)
            while len(list_stack) > indent:
                out.append(f"</{list_stack.pop()}>")
            while len(list_stack) < indent + 1:
                out.append("<ol>")
                list_stack.append("ol")
            out.append(f"<li>{inline_format(content)}</li>")
            i += 1
            continue

        # 普通段落
        close_lists(out, list_stack)
        out.append(f"<p>{inline_format(stripped)}</p>")
        i += 1

    if in_blockquote:
        out.append("</blockquote>")
    if in_table:
        out.append("</tbody></table>")
    close_lists(out, list_stack)
    if in_code:
        out.append("</code></pre>")

    toc_items: list[str] = []
    for level, text, anchor_id in headings:
        # 侧边导航仅展示二、三级标题，避免过长
        if level in (2, 3):
            toc_items.append(
                f'<li class="toc-lvl{level}"><a href="#{escape(anchor_id)}">{escape(text)}</a></li>'
            )
    toc_html = "<ul>" + "".join(toc_items) + "</ul>" if toc_items else "<p>无目录</p>"

    css = """
    :root {
      --text: #1f2328;
      --muted: #4b5563;
      --line: #d0d7de;
      --bg: #ffffff;
      --code-bg: #f3f6ff;
      --code-line: #9db4ff;
      --th-bg: #eef2f7;
      --accent: #1d4ed8;
      --accent-soft: #dbeafe;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Noto Serif SC", "Songti SC", "SimSun", "STSong", serif;
      line-height: 1.8;
      font-size: 17px;
    }
    .page {
      max-width: 1440px;
      margin: 22px auto 30px;
      padding: 0 20px 26px;
    }
    .layout {
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 24px;
      align-items: start;
    }
    .sidebar {
      position: sticky;
      top: 16px;
      max-height: calc(100vh - 32px);
      overflow: auto;
      border: 1px solid var(--line);
      background: #fafbfc;
      border-radius: 8px;
      padding: 14px 12px;
    }
    .sidebar h2 {
      margin: 0 0 8px;
      font-size: 1rem;
      border: none;
      padding: 0;
    }
    .sidebar ul {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .sidebar li {
      margin: 0;
      line-height: 1.45;
    }
    .sidebar .toc-lvl2 a {
      display: block;
      padding: 6px 8px;
      color: #1f2937;
      text-decoration: none;
      border-radius: 4px;
      font-size: 14px;
      font-weight: 600;
    }
    .sidebar .toc-lvl3 a {
      display: block;
      padding: 4px 8px 4px 18px;
      color: #374151;
      text-decoration: none;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 400;
    }
    .sidebar a:hover { background: var(--accent-soft); }
    .content {
      min-width: 0;
      padding: 0 8px;
    }
    h1, h2, h3, h4, h5, h6 {
      margin: 1.2em 0 0.5em;
      line-height: 1.4;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    h1 { font-size: 2.1em; border-bottom: 1px solid var(--line); padding-bottom: 0.3em; }
    h2 { font-size: 1.6em; border-bottom: 1px solid var(--line); padding-bottom: 0.25em; }
    h3 { font-size: 1.3em; }
    p { margin: 0.55em 0; }
    strong { color: #0f3f9f; font-weight: 700; }
    hr { border: none; border-top: 1px solid var(--line); margin: 1.4em 0; }
    code {
      background: var(--code-bg);
      border: 1px solid var(--code-line);
      color: #0b3b91;
      padding: 0.12em 0.4em;
      border-radius: 4px;
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
      font-size: 0.95em;
    }
    pre {
      background: var(--code-bg);
      border: 1px solid var(--code-line);
      border-left: 5px solid var(--accent);
      border-radius: 6px;
      padding: 12px 14px;
      overflow-x: auto;
      margin: 0.8em 0 1em;
    }
    pre code {
      border: none;
      background: transparent;
      padding: 0;
      font-size: 0.9em;
      line-height: 1.6;
    }
    blockquote {
      margin: 0.9em 0;
      padding: 0.35em 1em;
      border-left: 4px solid var(--accent);
      color: var(--muted);
      background: #f8fbff;
    }
    ul, ol { margin: 0.45em 0 0.65em 1.5em; padding: 0; }
    li { margin: 0.2em 0; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 0.9em 0 1.1em;
      table-layout: fixed;
      font-size: 15px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 8px 10px;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      background: var(--th-bg);
      font-weight: 700;
      text-align: left;
      color: #0f3f9f;
    }
    .header {
      margin-bottom: 22px;
      padding-bottom: 10px;
      border-bottom: 2px solid #111827;
    }
    .header .meta {
      color: var(--muted);
      font-size: 14px;
      margin-top: 6px;
    }
    @media (max-width: 1100px) {
      .layout {
        grid-template-columns: 1fr;
      }
      .sidebar {
        position: relative;
        top: auto;
        max-height: none;
      }
    }
    """

    body_content = "\n".join(out)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <div class="layout">
      <aside class="sidebar">
        <h2>导航目录</h2>
        {toc_html}
      </aside>
      <section class="content">
        <section class="header">
          <h1>{escape(title)}</h1>
        </section>
        {body_content}
      </section>
    </div>
  </main>
</body>
</html>
"""


def main() -> int:
    default_input = Path(__file__).with_name("Mango_测试使用说明.md")
    default_output = Path(__file__).with_name("Mango_测试使用说明.html")

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_input
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output

    if not input_path.exists():
        print(f"输入文件不存在: {input_path}")
        return 1

    md_text = input_path.read_text(encoding="utf-8")
    html_text = render_markdown(md_text, title=input_path.stem)
    output_path.write_text(html_text, encoding="utf-8")

    print(f"HTML 已生成: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
