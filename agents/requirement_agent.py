from models.schemas import AnalysisResult
from services.llm_service import LLMService
from services.ingestion_service import all_chunks

SYSTEM='''You are a senior business analyst and solution architect. Extract only evidence-grounded requirements from the supplied project material. Identify missing information, ambiguity, contradictions, assumptions and client clarification questions. Questions must be labeled business or technical. Never invent facts.'''

def run(project_id: str, llm: LLMService) -> AnalysisResult:
    chunks=all_chunks(project_id)
    context='\n\n'.join(f"SOURCE {c['id']}:\n{c['text']}" for c in chunks)
    if not context: raise ValueError('Upload at least one transcript or document first.')
    user=f'''Analyze the following project knowledge. Return JSON with keys requirements, gaps, assumptions, contradictions.
Each requirement: id,type,title,description,priority,source_refs,status.
Each gap: id,category,description,severity,business_impact,question,question_type,related_requirement_ids.
Requirement type must be business, functional, non-functional, integration, data, security, or operational.
Priority and severity must be high, medium, or low. Requirement status must be new.
Question type must be business or technical. source_refs and related_requirement_ids must be arrays of strings.
Assumptions and contradictions must be arrays of strings.
Use stable IDs like REQ-001 and GAP-001. Keep descriptions concise and avoid duplicate requirements.\n\n{context}'''
    return AnalysisResult.model_validate(llm.json_chat(SYSTEM,user))
