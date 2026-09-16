from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.diagram_agent import generate as generate_diagram
from agents.document_agent import generate as generate_document
from agents.requirement_agent import run as analyze_requirements
from services.llm_service import LLMService
from services.project_service import load_json, save_json


Action = Literal['analyze', 'document', 'diagram']


class WorkflowState(TypedDict, total=False):
    """Shared LangGraph state for one project operation."""

    project_id: str
    action: Action
    previous_analysis: dict
    analysis: dict
    doc_type: str
    document: str
    diagram_type: str
    diagram: str
    status: str


class RequirementAnalysisWorkflow:
    """LangGraph orchestration for the Phase-1 requirement-analysis POC.

    The graph deliberately keeps agent implementations framework-agnostic.
    LangGraph owns state and routing; agents own their domain prompts/logic.
    """

    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or LLMService()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(WorkflowState)

        graph.add_node('prepare', self._prepare)
        graph.add_node('requirement_agent', self._requirement_agent)
        graph.add_node('reconcile_changes', self._reconcile_changes)
        graph.add_node('persist_analysis', self._persist_analysis)
        graph.add_node('document_agent', self._document_agent)
        graph.add_node('diagram_agent', self._diagram_agent)

        graph.add_edge(START, 'prepare')
        graph.add_conditional_edges(
            'prepare',
            self._route_action,
            {
                'analyze': 'requirement_agent',
                'document': 'document_agent',
                'diagram': 'diagram_agent',
            },
        )

        graph.add_edge('requirement_agent', 'reconcile_changes')
        graph.add_edge('reconcile_changes', 'persist_analysis')
        graph.add_edge('persist_analysis', END)
        graph.add_edge('document_agent', END)
        graph.add_edge('diagram_agent', END)

        return graph.compile()

    def _prepare(self, state: WorkflowState) -> WorkflowState:
        project_id = state.get('project_id', '').strip()
        if not project_id:
            raise ValueError('project_id is required')

        action = state.get('action', 'analyze')
        if action not in {'analyze', 'document', 'diagram'}:
            raise ValueError(f'Unsupported workflow action: {action}')

        return {
            'previous_analysis': load_json(project_id, 'knowledge/analysis.json', {}),
            'status': f'prepared:{action}',
        }

    @staticmethod
    def _route_action(state: WorkflowState) -> Action:
        return state.get('action', 'analyze')

    def _requirement_agent(self, state: WorkflowState) -> WorkflowState:
        result = analyze_requirements(state['project_id'], self.llm)
        return {'analysis': result.model_dump(), 'status': 'requirements_analyzed'}

    def _reconcile_changes(self, state: WorkflowState) -> WorkflowState:
        current = state.get('analysis', {})
        previous = state.get('previous_analysis', {})

        if previous:
            old_by_title = {
                r.get('title', '').strip().lower(): r
                for r in previous.get('requirements', [])
                if r.get('title')
            }
            for req in current.get('requirements', []):
                old = old_by_title.get(req.get('title', '').strip().lower())
                if not old:
                    req['status'] = 'new'
                    continue
                req['status'] = (
                    'existing'
                    if req.get('description') == old.get('description')
                    else 'changed'
                )

        return {'analysis': current, 'status': 'changes_reconciled'}

    def _persist_analysis(self, state: WorkflowState) -> WorkflowState:
        analysis = state.get('analysis', {})
        save_json(state['project_id'], 'knowledge/analysis.json', analysis)
        return {'status': 'analysis_persisted'}

    def _document_agent(self, state: WorkflowState) -> WorkflowState:
        doc_type = state.get('doc_type', 'BRD')
        text = generate_document(state['project_id'], self.llm, doc_type)
        return {'document': text, 'status': f'document_generated:{doc_type}'}

    def _diagram_agent(self, state: WorkflowState) -> WorkflowState:
        diagram_type = state.get('diagram_type', 'Process Flow')
        code = generate_diagram(state['project_id'], self.llm, diagram_type)
        return {'diagram': code, 'status': f'diagram_generated:{diagram_type}'}

    def analyze(self, project_id: str) -> dict:
        result = self.graph.invoke({'project_id': project_id, 'action': 'analyze'})
        return result.get('analysis', {})

    def create_document(self, project_id: str, doc_type: str) -> str:
        result = self.graph.invoke(
            {'project_id': project_id, 'action': 'document', 'doc_type': doc_type}
        )
        return result.get('document', '')

    def create_diagram(self, project_id: str, diagram_type: str) -> str:
        result = self.graph.invoke(
            {
                'project_id': project_id,
                'action': 'diagram',
                'diagram_type': diagram_type,
            }
        )
        return result.get('diagram', '')

    def graph_mermaid(self) -> str:
        """Useful for the demo: return the orchestration graph as Mermaid."""
        return self.graph.get_graph().draw_mermaid()
