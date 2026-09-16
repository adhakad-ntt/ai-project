# Multi-Agent AI Requirement Analysis POC — Final

A runnable VS Code / Streamlit proof of concept for AI-assisted requirement analysis using LangGraph orchestration and a free API-key-based LLM endpoint for testing.

## Phase-1 capabilities
1. **Project workspace management** — create and switch projects; each project has isolated source, knowledge, output and diagram storage.
2. **Incremental knowledge management** — upload Teams transcripts/client documents; SHA-256 detects new, updated and unchanged files.
3. **Requirement and gap analysis** — extracts business/functional/NFR/integration/data/security/operational requirements; identifies assumptions, contradictions and business/technical clarification questions.
4. **Functional documentation** — generates BRD or user stories with unresolved items clearly marked.
5. **Diagram generation** — generates Mermaid process-flow, sequence and architecture diagrams.

Technical/API specification generation remains Phase 2.

## Architecture

```text
Streamlit UI
    |
    v
Application Orchestrator
    |
    v
LangGraph StateGraph
    |--------------------|--------------------|
    v                    v                    v
Requirement Agent   Document Agent       Diagram Agent
    |                    |                    |
    v                    v                    v
Change Reconcile     BRD/User Stories     Mermaid
    |
    v
Project-isolated Knowledge / RAG
    |
    v
Groq OpenAI-compatible LLM API
```

## Requirements
- Windows company laptop
- Python **3.11 or 3.12 recommended**
- VS Code + Python extension
- Network access to the approved LLM endpoint
- Groq API key for the default testing configuration

## Fastest Windows setup

1. Extract the ZIP.
2. Open the extracted `requirement_analysis_poc_final` folder in VS Code.
3. Double-click or run:

```text
setup_windows.bat
```

4. Open `.env` and replace:

```text
GROQ_API_KEY=replace_with_your_key
```

5. Run:

```text
run_app.bat
```

Or from the VS Code terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
# edit .env and enter the API key
python -m streamlit run app.py
```

## Default LLM configuration

```text
GROQ_MODEL=openai/gpt-oss-20b
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

The LLM integration is isolated in `services/llm_service.py`, so a future approved OpenAI-compatible endpoint can be substituted without rewriting the agents.

## Project layout

```text
requirement_analysis_poc_final/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── setup_windows.bat
├── run_app.bat
├── pytest.ini
├── agents/
│   ├── requirement_agent.py
│   ├── document_agent.py
│   └── diagram_agent.py
├── services/
│   ├── langgraph_workflow.py
│   ├── orchestrator.py
│   ├── llm_service.py
│   ├── ingestion_service.py
│   └── project_service.py
├── rag/
│   └── retriever.py
├── models/
│   └── schemas.py
├── data/
│   └── projects/
├── samples/
│   ├── sample_meeting_01.txt
│   └── sample_meeting_02.txt
└── tests/
    ├── test_project_service.py
    └── test_langgraph_workflow.py
```

## Recommended demo
1. Create project `Order Renewal Automation`.
2. Upload `samples/sample_meeting_01.txt`.
3. Run AI Analysis and review requirements + open questions.
4. Generate BRD and diagrams.
5. Upload `samples/sample_meeting_02.txt`.
6. Run AI Analysis again to demonstrate incremental knowledge and requirement/gap updates.
7. Regenerate the BRD and diagrams.
8. Create a second project to demonstrate project isolation.

## Tests

```powershell
pytest
```

## Security note
Do not upload confidential client data to an external LLM unless your company has explicitly approved that endpoint and usage. Do not commit `.env` or project source documents to Git.
