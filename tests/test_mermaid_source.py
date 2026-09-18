from utils.mermaid_source import normalize_mermaid


def test_decision_reference_and_parentheses_are_inside_quoted_labels():
    source = 'flowchart TD\nB --> C{Sender in allowlist?}<br/>REQ-001\nC --> D[Retry (back-off)<br/>REQ-004]'
    result = normalize_mermaid(source)
    assert 'C{"Sender in allowlist?<br/>REQ-001"}' in result
    assert 'D["Retry (back-off)<br/>REQ-004"]' in result
    assert normalize_mermaid(result) == result


def test_fences_sequence_and_styles():
    sequence = 'sequenceDiagram\nA->>B: Send [message] (REQ-001)'
    assert normalize_mermaid(f'```mermaid\n{sequence}\n```') == sequence
    source = 'flowchart TD\n%% A[comment]\nclassDef gap fill:#ffebcc;\nA[Gap?]:::gap'
    result = normalize_mermaid(source)
    assert '%% A[comment]\nclassDef gap fill:#ffebcc;' in result
    assert 'A["Gap?"]:::gap' in result
