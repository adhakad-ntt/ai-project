from __future__ import annotations
from pathlib import Path
import json, re, shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / 'data' / 'projects'
PROJECTS.mkdir(parents=True, exist_ok=True)

def slug(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]+','-',name.strip()).strip('-').lower()

def project_path(project_id: str) -> Path:
    return PROJECTS / project_id

def list_projects():
    out=[]
    for p in PROJECTS.iterdir():
        if p.is_dir() and (p/'project.json').exists():
            out.append(json.loads((p/'project.json').read_text(encoding='utf-8')))
    return sorted(out,key=lambda x:x.get('created_at',''))

def create_project(name: str, description: str=''):
    pid = slug(name)
    if not pid: raise ValueError('Project name is required')
    p=project_path(pid)
    if p.exists(): raise ValueError('Project already exists')
    for d in ['sources','knowledge','outputs','diagrams']:(p/d).mkdir(parents=True,exist_ok=True)
    meta={'id':pid,'name':name,'description':description,'created_at':datetime.utcnow().isoformat()+'Z'}
    (p/'project.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta

def load_json(project_id: str, rel: str, default):
    f=project_path(project_id)/rel
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else default

def save_json(project_id: str, rel: str, data):
    f=project_path(project_id)/rel; f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')

def reset_project(project_id: str):
    p=project_path(project_id)
    for rel in ['knowledge','outputs','diagrams']:
        d=p/rel
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True,exist_ok=True)
