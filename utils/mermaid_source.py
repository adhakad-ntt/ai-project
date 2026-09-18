"""Conservative repairs for common generated flowchart label errors."""

import re


_NODE = re.compile(
    r'(?P<id>\b[A-Za-z_][\w-]*\s*)'
    r'(?P<shape>\[(?:"[^"\n]*"|[^\[\]"\n]*)\]|\{(?:"[^"\n]*"|[^{}"\n]*)\})'
    r'(?P<refs>(?:<br\s*/?>\s*REQ-\d+(?:\s*,\s*REQ-\d+)*)*)',
    re.IGNORECASE,
)


def normalize_mermaid(source: str) -> str:
    source = source.strip()
    fenced = re.fullmatch(r'```(?:mermaid)?\s*\n(.*?)\n```', source, re.DOTALL | re.IGNORECASE)
    if fenced:
        source = fenced.group(1).strip()
    if not re.match(r'^(?:flowchart|graph)\s', source):
        return source

    def quote_label(match: re.Match) -> str:
        shape = match['shape']
        label = shape[1:-1]
        if label.startswith('"') and label.endswith('"'):
            label = label[1:-1]
        return f'{match["id"]}{shape[0]}"{label}{match["refs"]}"{shape[-1]}'

    lines = []
    for line in source.splitlines():
        # Limit repairs to node/edge statements and subgraph labels.
        if re.match(r'^\s*(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b)', line):
            lines.append(line)
        else:
            lines.append(_NODE.sub(quote_label, line))
    return '\n'.join(lines)
