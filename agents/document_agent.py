from services.llm_service import LLMService
from services.project_service import load_json, project_path
from rag.retriever import retrieve

SYSTEM='''You are a senior business analyst. Produce professional functional documentation grounded in the approved project requirements and gaps. Do not invent implementation detail. Mark unresolved items explicitly.'''

def generate(project_id: str, llm: LLMService, doc_type: str):
    analysis=load_json(project_id,'knowledge/analysis.json',{})
    evidence=retrieve(project_id,'business scope functional requirements actors workflows acceptance criteria',10)
    ctx='\n'.join(f"{x['id']}: {x['text']}" for x in evidence)
    if doc_type=='BRD':
        instruction='Create a concise BRD with Executive Summary, Business Problem, Objectives, Scope, Stakeholders/Actors if known, Functional Requirements, Non-Functional Requirements, Assumptions, Dependencies, Gaps/Open Questions, Acceptance Considerations.'
    else:
        instruction='Create user stories grouped by capability. Use As a / I want / So that and include acceptance criteria. Clearly flag unresolved dependencies.'
    text=llm.chat(SYSTEM,f'{instruction}\n\nSTRUCTURED ANALYSIS:\n{analysis}\n\nSOURCE EVIDENCE:\n{ctx}',0.2)
    out=project_path(project_id)/'outputs'/f"{doc_type.lower().replace(' ','_')}.md"; out.write_text(text,encoding='utf-8')
    return text
