from __future__ import annotations
import truststore

# Use the operating system's trusted certificates, including company CAs.
truststore.inject_into_ssl()

import streamlit as st
from services.project_service import list_projects, create_project, load_json, project_path
from services.ingestion_service import ingest_upload, ingest_transcript
from services.orchestrator import Orchestrator
from services.llm_service import LLMService
from services.chat_service import agent_reply, new_conversation, list_conversations, save_conversation
from services.chat_actions import apply_change, change_review_rows
from services.llm_service import RateLimitError, InvalidLLMResponse
from utils.analysis_export import analysis_text
from utils.mermaid_source import normalize_mermaid
from utils.copy_button import copy_menu
import requests
from utils.ui import apply_styles, project_header

st.set_page_config(page_title='Clarity | Requirements workspace', page_icon=':material/account_tree:', layout='wide')
apply_styles()
st.session_state.setdefault('active_chats', {})
st.session_state.setdefault('chat_open', True)
st.session_state.setdefault('pending_change', None)

llm=LLMService()
with st.sidebar:
    st.html('<div class="workspace-brand">◈ Clarity</div>')
    st.caption('From project knowledge to clear requirements.')
    st.divider()
    st.subheader('Workspace')
    projects=list_projects()
    labels=['-- Create / Select --']+[f"{p['name']} ({p['id']})" for p in projects]
    sel=st.selectbox('Project',labels)
    if llm.configured():
        st.caption('● AI configured')
    else:
        st.warning('API key not configured')
    with st.expander('Connection details'):
        st.caption(f'Model: {llm.model}')
        st.caption('A configured key is required for analysis and chat.')

with st.sidebar.expander('Create New Project',expanded=not bool(projects)):
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
    project_header('Turn project knowledge into clarity',
                   'Capture requirements, resolve open questions, and build documents and diagrams in one workspace.')
    st.info('Create or select a project to continue. Each project stores isolated sources, analysis, documents and diagrams.')
    for column, title, body in zip(st.columns(3),
            ['01 · Add your knowledge', '02 · Review the analysis', '03 · Share the outcome'],
            ['Upload meeting transcripts and project documents.',
             'Explore requirements, gaps and clarification questions.',
             'Generate documents and diagrams, then refine them with your assistant.']):
        with column, st.container(border=True):
            st.markdown(f'**{title}**')
            st.write(body)
    st.stop()

selected_project = next(p for p in projects if p['id'] == pid)
project_header(selected_project['name'], selected_project.get('description') or 'Your project knowledge, decisions and deliverables in one place.')
summary_analysis = load_json(pid, 'knowledge/analysis.json', {})
summary_sources = load_json(pid, 'knowledge/sources.json', {})
for column, label, value in zip(st.columns(4),
        ['Source documents', 'Requirements', 'Clarification questions', 'Saved diagrams'],
        [len(summary_sources), len(summary_analysis.get('requirements', [])),
         len(summary_analysis.get('gaps', [])), len(list((project_path(pid) / 'diagrams').glob('*.mmd')))]):
    column.metric(label, value)

with st.container(horizontal=True, horizontal_alignment='right'):
    if st.button('Minimize chat' if st.session_state['chat_open'] else 'Open chat', key='toggle_chat',
                 icon=':material/right_panel_close:' if st.session_state['chat_open'] else ':material/right_panel_open:'):
        st.session_state['chat_open'] = not st.session_state['chat_open']
        st.rerun()
# Reserve the full page width for reviewing long requirement descriptions.
review_panel = st.container()
if st.session_state['chat_open']:
    workspace, chat_panel = st.columns([2.6, 1], gap='large')
else:
    workspace = st.container()
with workspace:
    tabs=st.tabs(['Knowledge','Requirements & Gaps','Documents','Diagrams'])
with tabs[0]:
    st.subheader('Project knowledge')
    st.caption('Upload documents, paste a Teams transcript, or add both. Analysis uses all saved project knowledge.')
    uploads=st.file_uploader('Upload Teams transcript or client documents',type=['txt','md','pdf','docx','csv'],accept_multiple_files=True, key=f'knowledge_uploads_{pid}')
    st.markdown('#### Paste a Teams transcript')
    transcript_title = st.text_input('Transcript title', value='Teams meeting', key=f'transcript_title_{pid}',
                                    help='Use a different title for each meeting. Reusing a title updates that saved transcript.')
    transcript_text = st.text_area('Transcript text', height=220, key=f'transcript_text_{pid}',
                                  placeholder='Paste the meeting transcript here, including speaker names and timestamps if available.')
    st.caption('Save with Ingest / Update Knowledge, then open Requirements & Gaps and run AI Analysis.')
    if st.button('Ingest / Update Knowledge',disabled=not uploads and not transcript_text.strip(), type='primary', icon=':material/upload_file:'):
        for f in uploads:
            try:
                result = ingest_upload(pid,f)
                st.success(f"{f.name}: {result['change']}")
            except Exception as e: st.error(f'{f.name}: {e}')
        if transcript_text.strip():
            try:
                result = ingest_transcript(pid, transcript_title, transcript_text)
                st.success(f"Transcript {transcript_title}: {result['change']}. Run AI Analysis to include the saved knowledge.")
            except Exception as e:
                st.error(f'Transcript: {e}')
    sources=load_json(pid,'knowledge/sources.json',{})
    if sources: st.dataframe([{'File':k,'Status':v.get('change'),'Updated':v.get('updated_at'),'Passages':len(v.get('chunks',[]))} for k,v in sources.items()],width='stretch', hide_index=True)
    else: st.info('No project knowledge yet. Upload a document or paste a transcript above to get started.')

with tabs[1]:
    st.subheader('Requirement and Gap Analysis')
    st.write('Generates structured requirements, technical/business gaps, assumptions and contradictions.')
    if st.button('Run AI Analysis', type='primary', icon=':material/auto_awesome:'):
        try:
            with st.spinner('Analyzing project knowledge… Temporary rate limits are retried automatically; this may take a minute.'): analysis=Orchestrator().analyze(pid)
            st.success('Analysis completed'); st.session_state['analysis']=analysis
        except Exception as e: st.error(str(e))
    analysis=load_json(pid,'knowledge/analysis.json',{})
    if analysis:
        with st.expander('Preview text to share'):
            st.code(analysis_text(analysis), language=None, wrap_lines=True, height=350)
        for section, title, label in [
            ('requirements', 'Requirements', 'Copy requirements'),
            ('gaps', 'Gaps / Clarification Questions', 'Copy gaps'),
        ]:
            with st.container(horizontal=True, vertical_alignment='center'):
                st.markdown(f'### {title}')
                copy_menu(analysis_text(analysis, section=section),
                          key=f'copy_{section}_{pid}', label=label)
            st.dataframe(analysis.get(section, []), width='stretch', hide_index=True)
        for key, title in [('assumptions', 'Assumptions'), ('contradictions', 'Contradictions')]:
            st.markdown(f'### {title}')
            items = analysis.get(key) or []
            if items:
                for index, item in enumerate(items, start=1):
                    st.markdown(f'{index}. {item}')
            else:
                st.caption(f'No {key} identified.')
    else:
        st.info('Your analysis will appear here. Add project knowledge, then run AI analysis.')

with tabs[2]:
    st.subheader('Functional Documentation')
    st.caption('Create a shareable document from the current project requirements and open questions.')
    dtype=st.radio('Output',['BRD','User Stories'],horizontal=True)
    if st.button('Generate Document', type='primary', icon=':material/description:'):
        try:
            with st.spinner('Preparing your document...'): Orchestrator().generate_document(pid,dtype)
        except Exception as e: st.error(str(e))
    document_name = dtype.lower().replace(' ', '_')
    document_path = project_path(pid) / 'outputs' / f'{document_name}.md'
    if document_path.exists():
        document_text = document_path.read_text(encoding='utf-8')
        st.download_button(
            f'Download {dtype} (.md)',
            data=document_text,
            file_name=f'{pid}_{document_name}.md',
            mime='text/markdown; charset=utf-8',
            icon=':material/download:',
            on_click='ignore',
        )
        with st.container(key='document_preview'):
            st.markdown(document_text)
    else:
        st.info(f'No {dtype} generated yet. Generate a document to preview and download it here.')

with tabs[3]:
    st.subheader('Project diagrams')
    st.caption('Visualize your process, interactions and architecture. Ask the assistant to refine labels or flows.')
    d=st.selectbox('Diagram type',['Process Flow','Sequence','Architecture'])
    if st.button('Generate / Update Diagram', type='primary', icon=':material/account_tree:'):
        try:
            with st.spinner('Generating diagram...'):
                Orchestrator().generate_diagram(pid,d)
        except Exception as e: st.error(str(e))
    diagram_path = project_path(pid) / 'diagrams' / f"{d.lower().replace(' ', '_')}.mmd"
    if diagram_path.exists():
        diagram_code = normalize_mermaid(diagram_path.read_text(encoding='utf-8'))
        st.mermaid_chart(diagram_code, width='stretch')
        with st.expander('Mermaid source'):
            st.code(diagram_code, language='mermaid')
        st.download_button('Download Mermaid source', diagram_code,
                           file_name=diagram_path.name, mime='text/plain')
    else:
        st.info('No diagram saved for this view. Generate one from your project analysis.')

if st.session_state['chat_open']:
    with chat_panel, st.container(key='assistant_panel'):
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
                if pending['target'] == 'diagram':
                    st.write(f"Diagram: {pending['after']['diagram_type']}")
                    for label, version in [('Existing diagram', 'before'), ('Proposed diagram', 'after')]:
                        st.markdown(f'**{label}**')
                        st.mermaid_chart(normalize_mermaid(pending[version]['code']), width='stretch')
                        with st.expander(f'{label} source'):
                            st.code(pending[version]['code'], language='mermaid')
                    st.caption('Review the labels and connections before approving. Regenerating this diagram later replaces these edits.')
                else:
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
