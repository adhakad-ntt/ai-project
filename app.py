from __future__ import annotations
import streamlit as st
from services.project_service import list_projects, create_project, load_json
from services.ingestion_service import ingest_upload
from services.orchestrator import Orchestrator
from services.llm_service import LLMService

st.set_page_config(page_title='AI Requirement Analysis POC',layout='wide')
st.title('Multi-Agent AI Requirement Analysis POC')
st.caption('Project workspace • LangGraph orchestration • incremental knowledge • requirements/gaps • BRD/user stories • Mermaid diagrams')

llm=LLMService()
with st.sidebar:
    st.header('Workspace')
    projects=list_projects()
    labels=['-- Create / Select --']+[f"{p['name']} ({p['id']})" for p in projects]
    sel=st.selectbox('Project',labels)
    st.caption(f"LLM: {llm.model}")
    st.success('API key configured') if llm.configured() else st.warning('API key not configured')

with st.expander('Create New Project',expanded=not bool(projects)):
    name=st.text_input('Project name')
    desc=st.text_area('Description')
    if st.button('Create Project'):
        try:
            create_project(name, desc)
            st.success('Project created.')
            st.rerun()
        except Exception as e:
            st.error(str(e))

pid=None
if sel!='-- Create / Select --': pid=projects[labels.index(sel)-1]['id']
if not pid:
    st.info('Create or select a project to continue. Each project stores isolated sources, analysis, documents and diagrams.')
    st.stop()

tabs=st.tabs(['1. Knowledge','2. Requirements & Gaps','3. Functional Docs','4. Diagrams','5. LangGraph','6. Demo Flow'])
with tabs[0]:
    st.subheader('Incremental Knowledge Management')
    uploads=st.file_uploader('Upload Teams transcript or client documents',type=['txt','md','pdf','docx','csv'],accept_multiple_files=True)
    if st.button('Ingest / Update Knowledge',disabled=not uploads):
        for f in uploads:
            try: st.write(ingest_upload(pid,f))
            except Exception as e: st.error(f'{f.name}: {e}')
    sources=load_json(pid,'knowledge/sources.json',{})
    if sources: st.dataframe([{'file':k,'change':v.get('change'),'updated_at':v.get('updated_at'),'chunks':len(v.get('chunks',[]))} for k,v in sources.items()],use_container_width=True)

with tabs[1]:
    st.subheader('Requirement and Gap Analysis')
    st.write('Generates structured requirements, technical/business gaps, assumptions and contradictions.')
    if st.button('Run AI Analysis'):
        try:
            with st.spinner('Analyzing project knowledge...'): analysis=Orchestrator().analyze(pid)
            st.success('Analysis completed'); st.session_state['analysis']=analysis
        except Exception as e: st.error(str(e))
    analysis=load_json(pid,'knowledge/analysis.json',{})
    if analysis:
        st.markdown('### Requirements'); st.dataframe(analysis.get('requirements',[]),use_container_width=True)
        st.markdown('### Gaps / Clarification Questions'); st.dataframe(analysis.get('gaps',[]),use_container_width=True)
        c1,c2=st.columns(2); c1.write({'assumptions':analysis.get('assumptions',[])}); c2.write({'contradictions':analysis.get('contradictions',[])})

with tabs[2]:
    st.subheader('Functional Documentation')
    dtype=st.radio('Output',['BRD','User Stories'],horizontal=True)
    if st.button('Generate Document'):
        try:
            with st.spinner('Generating through LangGraph...'): text=Orchestrator().generate_document(pid,dtype)
            st.session_state['doc']=text
        except Exception as e: st.error(str(e))
    if 'doc' in st.session_state: st.markdown(st.session_state['doc'])

with tabs[3]:
    st.subheader('Mermaid Diagram Generation')
    d=st.selectbox('Diagram type',['Process Flow','Sequence','Architecture'])
    if st.button('Generate / Update Diagram'):
        try: st.session_state['diagram']=Orchestrator().generate_diagram(pid,d)
        except Exception as e: st.error(str(e))
    if 'diagram' in st.session_state:
        st.code(st.session_state['diagram'],language='mermaid')
        st.caption('Paste this Mermaid code into Mermaid Live Editor or a Mermaid-enabled renderer.')

with tabs[4]:
    st.subheader('LangGraph Orchestration')
    st.write('The application routes AI operations through a compiled LangGraph StateGraph. Agents remain independent while LangGraph manages workflow state and conditional routing.')
    try:
        st.code(Orchestrator().graph_mermaid(), language='mermaid')
    except Exception as e:
        st.info(f'Graph visualization unavailable: {e}')

with tabs[5]:
    st.subheader('End-to-End Demo Flow')
    st.markdown('''1. Create a new project workspace.  
2. Upload the first Teams transcript and/or client document.  
3. Ingest content into the isolated project knowledge base.  
4. Run requirement and gap analysis.  
5. Review business and technical clarification questions.  
6. Upload a later transcript containing answers or changed scope.  
7. Re-ingest; unchanged files are ignored and updated files are detected by hash.  
8. Re-run analysis to refresh requirements and gap status.  
9. Generate BRD or user stories.  
10. Generate/update process, sequence, and architecture Mermaid diagrams.''')
