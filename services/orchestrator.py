from __future__ import annotations

from services.langgraph_workflow import RequirementAnalysisWorkflow
from services.llm_service import LLMService


class Orchestrator:
    """Application-facing facade over the LangGraph workflow."""

    def __init__(self, llm: LLMService | None = None):
        self.workflow = RequirementAnalysisWorkflow(llm=llm)

    def analyze(self, project_id: str) -> dict:
        return self.workflow.analyze(project_id)

    def generate_document(self, project_id: str, doc_type: str) -> str:
        return self.workflow.create_document(project_id, doc_type)

    def generate_diagram(self, project_id: str, diagram_type: str) -> str:
        return self.workflow.create_diagram(project_id, diagram_type)

    def graph_mermaid(self) -> str:
        return self.workflow.graph_mermaid()
