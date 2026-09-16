from services.llm_service import LLMService
from services.project_service import load_json, project_path

SYSTEM='''You generate valid Mermaid only. Base diagrams strictly on provided requirements. Do not invent systems. Return Mermaid code without markdown fences.'''

def generate(project_id: str, llm: LLMService, diagram_type: str):
    analysis=load_json(project_id,'knowledge/analysis.json',{})
    instructions={
        'Process Flow':'Create a Mermaid flowchart showing the business/process flow.',
        'Sequence':'Create a Mermaid sequenceDiagram using only known actors/systems and interactions.',
        'Architecture':'Create a Mermaid flowchart showing high-level logical architecture and integrations supported by evidence.'}
    code=llm.chat(SYSTEM,f"{instructions[diagram_type]}\n\nANALYSIS:\n{analysis}",0.1).strip()
    out=project_path(project_id)/'diagrams'/f"{diagram_type.lower().replace(' ','_')}.mmd"; out.write_text(code,encoding='utf-8')
    return code
