from __future__ import annotations
import streamlit as st
from services.project_service import list_projects, create_project, load_json, project_path
from services.ingestion_service import ingest_upload
from services.orchestrator import Orchestrator
from services.llm_service import LLMService
from services.chat_service import agent_reply, new_conversation, list_conversations, save_conversation
from services.chat_actions import apply_change, change_review_rows
from services.llm_service import RateLimitError, InvalidLLMResponse
import requests

st.set_page_config(page_title='AI Requirement Analysis POC',layout='wide')
st.session_state.setdefault('active_chats', {})
st.session_state.setdefault('chat_open', True)
st.session_state.setdefault('pending_change', None)
st.title('Multi-Agent AI Requirement Analysis POC')
st.caption('Project workspace • LangGraph orchestration • incremental knowledge • requirements/gaps • BRD/user stories • Mermaid diagrams')

llm=LLMService()
with st.sidebar:
    st.header('Workspace')
    projects=list_projects()
    labels=['-- Create / Select --']+[f"{p['name']} ({p['id']})" for p in projects]
    sel=st.selectbox('Project',labels)
    st.caption(f"LLM: {llm.model}")
    if llm.configured():
        st.success('API key configured')
    else:
        st.warning('API key not configured')

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

with st.container(horizontal=True, horizontal_alignment='right'):
    if st.button('Minimize chat' if st.session_state['chat_open'] else 'Open chat', key='toggle_chat',
                 icon=':material/right_panel_close:' if st.session_state['chat_open'] else ':material/right_panel_open:'):
        st.session_state['chat_open'] = not st.session_state['chat_open']
        st.rerun()
# Reserve the full page width for reviewing long requirement descriptions.
review_panel = st.container()
if st.session_state['chat_open']:
    workspace, chat_panel = st.columns([2.2, 1], gap='large')
else:
    workspace = st.container()
with workspace:
    tabs=st.tabs(['1. Knowledge','2. Requirements & Gaps','3. Functional Docs','4. Diagrams'])
with tabs[0]:
    st.subheader('Incremental Knowledge Management')
    uploads=st.file_uploader('Upload Teams transcript or client documents',type=['txt','md','pdf','docx','csv'],accept_multiple_files=True)
    if st.button('Ingest / Update Knowledge',disabled=not uploads):
        for f in uploads:
            try: st.write(ingest_upload(pid,f))
            except Exception as e: st.error(f'{f.name}: {e}')
    sources=load_json(pid,'knowledge/sources.json',{})
    if sources: st.dataframe([{'file':k,'change':v.get('change'),'updated_at':v.get('updated_at'),'chunks':len(v.get('chunks',[]))} for k,v in sources.items()],width='stretch')

with tabs[1]:
    st.subheader('Requirement and Gap Analysis')
    st.write('Generates structured requirements, technical/business gaps, assumptions and contradictions.')
    if st.button('Run AI Analysis'):
        try:
            with st.spinner('Analyzing project knowledge… Temporary rate limits are retried automatically; this may take a minute.'): analysis=Orchestrator().analyze(pid)
            st.success('Analysis completed'); st.session_state['analysis']=analysis
        except Exception as e: st.error(str(e))
    analysis=load_json(pid,'knowledge/analysis.json',{})
    if analysis:
        st.markdown('### Requirements'); st.dataframe(analysis.get('requirements',[]),width='stretch')
        st.markdown('### Gaps / Clarification Questions'); st.dataframe(analysis.get('gaps',[]),width='stretch')
        for key, title in [('assumptions', 'Assumptions'), ('contradictions', 'Contradictions')]:
            st.markdown(f'### {title}')
            items = analysis.get(key) or []
            if items:
                for index, item in enumerate(items, start=1):
                    st.markdown(f'{index}. {item}')
            else:
                st.caption(f'No {key} identified.')

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
        try:
            with st.spinner('Generating diagram...'):
                Orchestrator().generate_diagram(pid,d)
        except Exception as e: st.error(str(e))
    diagram_path = project_path(pid) / 'diagrams' / f"{d.lower().replace(' ', '_')}.mmd"
    if diagram_path.exists():
        diagram_code = diagram_path.read_text(encoding='utf-8').strip()
        if diagram_code.startswith('```') and diagram_code.endswith('```'):
            diagram_code = '\n'.join(diagram_code.splitlines()[1:-1]).strip()
        st.mermaid_chart(diagram_code, width='stretch')
        with st.expander('Mermaid source'):
            st.code(diagram_code, language='mermaid')
        st.download_button('Download Mermaid source', diagram_code,
                           file_name=diagram_path.name, mime='text/plain')

if st.session_state['chat_open']:
    with chat_panel, st.container(border=True):
        st.subheader('Project assistant', anchor=False)
        project_name = next(p['name'] for p in projects if p['id'] == pid)
        st.caption(f'{project_name} · Start fresh or continue a recent chat')
        active_chats = st.session_state['active_chats']
        if pid not in active_chats:
            active_chats[pid] = new_conversation()
        if st.button('New chat', key='new_chat', icon=':material/edit_square:', width='stretch'):
            st.session_state['pending_change'] = None
            active_chats[pid] = new_conversation()
            st.rerun()
        with st.expander('Recent chats', expanded=False):
            recent = list_conversations(pid)
            if not recent:
                st.caption('Your conversations will appear here.')
            for chat in recent:
                if st.button(chat['title'], key=f"recent_{pid}_{chat['id']}",
                             help=chat['updated_at'] or 'Earlier saved conversation', width='stretch'):
                    active_chats[pid] = chat
                    st.session_state['pending_change'] = None
                    st.rerun()
        conversation = active_chats[pid]
        pending = st.session_state['pending_change']
        if pending and (pending['project_id'], pending['conversation_id']) != (pid, conversation['id']):
            st.session_state['pending_change'] = pending = None
        history = conversation['messages']
        st.caption(conversation['title'])
        messages = st.container(height=420)
        with messages:
            welcome = st.empty()
            if not history:
                welcome.info('Ask about requirements, open questions, or uploaded documents.')
            for message in history:
                with st.chat_message(message['role']):
                    st.markdown(message['content'])
        st.caption('Every project change requires your approval. Approvals apply once to the displayed change.')
        if notice := st.session_state.pop('change_notice', None):
            st.info(notice)
        if pending:
            with review_panel, st.container(border=True):
                st.markdown('**Review proposed change**')
                st.caption(f'Project: {project_name} | Nothing is saved until you approve this proposal.')
                st.write('Project description' if pending['target'] == 'project_description'
                         else f"Requirement {pending['after']['id']}")
                st.caption('Existing information → Proposed change. Changed fields appear first; unchanged fields provide context.')
                st.table(change_review_rows(pending), hide_index=True, hide_header=False, width='stretch')
                if pending['target'] == 'requirement':
                    related_gaps = [
                        {'ID': gap['id'], 'Question': gap.get('question', ''),
                         'Severity': gap.get('severity', ''), 'Business impact': gap.get('business_impact', '')}
                        for gap in pending['snapshot'].get('gaps', [])
                        if pending['after']['id'] in gap.get('related_requirement_ids', [])
                    ]
                    if related_gaps:
                        st.caption('Related clarification questions (for context; this approval does not change them)')
                        st.table(related_gaps, hide_index=True, hide_header=False, width='stretch')
                    st.caption('This approved requirement will be preserved when analysis is rerun. Existing documents and diagrams must be regenerated separately.')
                if st.button('Approve change', key=f"approve_{pending['id']}", type='primary'):
                    try:
                        apply_change(pending, pid, conversation['id'], approved=True)
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
                    else:
                        st.session_state['pending_change'] = None
                        st.session_state['change_notice'] = 'Approved change applied.'
                        try:
                            active_chats[pid] = save_conversation(pid, conversation,
                                'Approve the displayed change', 'Approved change applied.')
                        except OSError:
                            st.session_state['change_notice'] += ' The chat receipt could not be saved; the project change was saved.'
                        st.rerun()
                if st.button('Reject change', key=f"reject_{pending['id']}"):
                    st.session_state['pending_change'] = None
                    st.session_state['change_notice'] = 'Change rejected. Project data was not changed.'
                    st.rerun()
        prompt = st.chat_input(
            'Ask about this project...', key=f"project_chat_{pid}_{conversation['id']}",
            disabled=not llm.configured() or pending is not None, submit_mode='disable',
        )
        if not llm.configured():
            st.caption('Configure your Groq API key to start chatting.')
        if prompt and pending is None:
            welcome.empty()
            with messages:
                with st.chat_message('user'):
                    st.markdown(prompt)
                try:
                    with st.spinner('Reviewing project context...'):
                        answer, proposal = agent_reply(pid, prompt, llm, history, conversation['id'])
                    active_chats[pid] = save_conversation(pid, conversation, prompt, answer)
                    st.session_state['pending_change'] = proposal
                except (RateLimitError, InvalidLLMResponse) as exc:
                    st.error(str(exc))
                except requests.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else 'unknown'
                    st.error(f'AI request failed (HTTP {status}). Check the configured model and account access, or try a shorter conversation. Your saved chat is unchanged.')
                except RuntimeError as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error('Could not read project context or save the response. Your saved chat is unchanged. Please retry.')
                else:
                    st.rerun()
