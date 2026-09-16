from services.langgraph_workflow import RequirementAnalysisWorkflow


class FakeLLM:
    def configured(self):
        return True

    def json_chat(self, system, user):
        return {
            'requirements': [
                {
                    'id': 'REQ-001',
                    'type': 'functional',
                    'title': 'Create order',
                    'description': 'The system shall create an order.',
                    'priority': 'high',
                    'source_refs': ['meeting.txt#chunk-1'],
                    'status': 'new',
                }
            ],
            'gaps': [],
            'assumptions': [],
            'contradictions': [],
        }

    def chat(self, system, user, temperature=0.1):
        if 'Mermaid' in system:
            return 'flowchart LR\nA --> B'
        return '# Generated document'


def test_graph_can_compile():
    workflow = RequirementAnalysisWorkflow(llm=FakeLLM())
    mermaid = workflow.graph_mermaid()
    assert 'prepare' in mermaid
    assert 'requirement_agent' in mermaid
    assert 'document_agent' in mermaid
    assert 'diagram_agent' in mermaid
