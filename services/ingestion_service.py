from __future__ import annotations
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from pypdf import PdfReader
from docx import Document
from services.project_service import project_path, load_json, save_json

TEXT_TYPES={'.txt','.md','.csv'}

def extract_text(path: Path) -> str:
    ext=path.suffix.lower()
    if ext in TEXT_TYPES: return path.read_text(encoding='utf-8',errors='ignore')
    if ext=='.pdf': return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)
    if ext=='.docx': return '\n'.join(p.text for p in Document(str(path)).paragraphs)
    raise ValueError(f'Unsupported file type: {ext}')

def chunk_text(text: str, size: int=1800, overlap: int=250):
    text=' '.join(text.split())
    if not text:return []
    chunks=[]; i=0
    while i<len(text):
        chunks.append(text[i:i+size]); i += max(1,size-overlap)
    return chunks

def ingest_upload(project_id: str, uploaded_file):
    p=project_path(project_id); sources=p/'sources'; sources.mkdir(exist_ok=True)
    raw=uploaded_file.getvalue(); digest=sha256(raw).hexdigest(); target=sources/uploaded_file.name
    registry=load_json(project_id,'knowledge/sources.json',{})
    old=registry.get(uploaded_file.name)
    change='unchanged' if old and old.get('sha256')==digest else ('updated' if old else 'new')
    if change=='unchanged': return {'file':uploaded_file.name,'change':'unchanged','chunks_added':0}
    target.write_bytes(raw)
    text=extract_text(target); chunks=chunk_text(text)
    registry[uploaded_file.name]={'sha256':digest,'updated_at':datetime.utcnow().isoformat()+'Z','change':change,'text':text,'chunks':chunks}
    save_json(project_id,'knowledge/sources.json',registry)
    return {'file':uploaded_file.name,'change':change,'chunks_added':len(chunks)}

def all_chunks(project_id: str):
    registry=load_json(project_id,'knowledge/sources.json',{})
    out=[]
    for fname,meta in registry.items():
        for i,c in enumerate(meta.get('chunks',[])):
            out.append({'id':f'{fname}#chunk-{i+1}','source':fname,'text':c})
    return out
