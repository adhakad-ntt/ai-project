"""Readable analysis text for copying into emails and messages."""


def analysis_text(analysis: dict, *, section: str | None = None) -> str:
    lines = ['Requirement and Gap Analysis'] if section is None else []
    for key, title in [
        ('requirements', 'Requirements'),
        ('gaps', 'Gaps / Clarification Questions'),
        ('assumptions', 'Assumptions'),
        ('contradictions', 'Contradictions'),
    ]:
        if section is not None and key != section:
            continue
        lines.extend(['', title, '=' * len(title)])
        items = analysis.get(key) or []
        if not items:
            lines.append('None identified.')
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                lines.append(f'{index}.')
                for field, value in item.items():
                    if field.startswith('_'):
                        continue
                    label = field.replace('_', ' ').capitalize()
                    if isinstance(value, list):
                        value = '; '.join(str(part) for part in value)
                    lines.append(f'   {label}: {value if value is not None else ""}')
                lines.append('')
            else:
                lines.append(f'{index}. {item}')
    return '\n'.join(lines).strip()
