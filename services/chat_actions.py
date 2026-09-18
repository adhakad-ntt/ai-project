"""Prepare changes without writes; execute only an explicitly approved proposal."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
from uuid import uuid4

from models.schemas import Requirement
from services.project_service import load_json, project_path


def change_review_rows(proposal: dict) -> list[dict]:
    """Display the exact approved values, with changed fields first."""
    def display(value):
        if value is None or value == '':
            return '(Not set)'
        if isinstance(value, list):
            value = '\n'.join(value) if value else '(None)'
        # st.table supports Markdown; preserve source text as literal content.
        return re.sub(r'([\\`*_{}\[\]()<>#+.!|~:$-])', r'\\\1', str(value))

    if proposal['target'] == 'project_description':
        return [{'Field': 'Description', 'Existing information': display(proposal['before']),
                 'Proposed change': display(proposal['after']), 'Change': 'Updated'}]
    before, after = proposal['before'] or {}, proposal['after']
    labels = {'id': 'Requirement ID', 'title': 'Title', 'description': 'Description',
              'type': 'Type', 'priority': 'Priority', 'status': 'Status',
              'source_refs': 'Source references'}
    rows = []
    for key, label in labels.items():
        state = ('Added' if key not in before else
                 'Unchanged' if before[key] == after.get(key) else 'Updated')
        rows.append({'Field': label, 'Existing information': display(before.get(key)),
                     'Proposed change': display(after.get(key)), 'Change': state})
    return sorted(rows, key=lambda row: row['Change'] == 'Unchanged')


def prepare_change(project_id: str, conversation_id: str, change: dict) -> dict:
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', project_id):
        raise ValueError('Invalid project ID.')
    if not isinstance(change, dict) or set(change) != {'target', 'value'}:
        raise ValueError('Invalid change proposal. Please request one change at a time.')
    target, value = change['target'], change['value']
    if target == 'project_description':
        if not isinstance(value, str) or not value.strip():
            raise ValueError('A project description is required.')
        relative = 'project.json'
        current = load_json(project_id, relative, {})
        if not current:
            raise ValueError('Project no longer exists.')
        before = current.get('description', '')
    elif target == 'requirement':
        if not isinstance(value, dict) or set(value) - set(Requirement.model_fields):
            raise ValueError('Invalid requirement fields.')
        value = Requirement.model_validate(value).model_dump()
        if not all(value[key].strip() for key in ('id', 'title', 'description')):
            raise ValueError('Requirement ID, title and description are required.')
        relative = 'knowledge/analysis.json'
        current = load_json(project_id, relative, {})
        matches = [r for r in current.get('requirements', []) if r['id'] == value['id']]
        if len(matches) > 1:
            raise ValueError('Duplicate requirement ID; resolve it before editing.')
        before = matches[0] if matches else None
    else:
        raise ValueError('Only project descriptions and requirements can be changed from chat.')
    if before == value:
        raise ValueError('The proposed value is already saved.')
    return {'id': str(uuid4()), 'project_id': project_id, 'conversation_id': conversation_id,
            'target': target, 'relative': relative, 'snapshot': deepcopy(current),
            'before': deepcopy(before), 'after': value, 'status': 'pending'}


def apply_change(proposal: dict, project_id: str, conversation_id: str, *, approved: bool = False) -> None:
    if approved is not True or proposal['status'] != 'pending':
        raise ValueError('This change requires a fresh approval.')
    if (proposal['project_id'], proposal['conversation_id']) != (project_id, conversation_id):
        raise ValueError('This approval belongs to another project or conversation.')
    checked = prepare_change(project_id, conversation_id,
                             {'target': proposal['target'], 'value': proposal['after']})
    if checked['snapshot'] != proposal['snapshot']:
        raise ValueError('Project data changed since this preview. Reject it and request a fresh proposal.')
    updated = deepcopy(checked['snapshot'])
    if proposal['target'] == 'project_description':
        updated['description'] = checked['after']
    else:
        value = checked['after']
        requirements = updated.setdefault('requirements', [])
        existing = next((i for i, r in enumerate(requirements) if r['id'] == value['id']), None)
        if existing is None:
            requirements.append(value)
        else:
            requirements[existing] = value
        updated.setdefault('_chat_requirement_overrides', {})[value['id']] = value
    updated.setdefault('_chat_changes', []).append({
        'proposal_id': proposal['id'], 'conversation_id': conversation_id,
        'approved_at': datetime.now(timezone.utc).isoformat(),
        'target': proposal['target'], 'before': checked['before'], 'after': checked['after'],
    })
    path = project_path(project_id) / checked['relative']
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    proposal['status'] = 'applied'
