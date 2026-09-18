"""Browser clipboard control with a manual-copy fallback."""

from streamlit.components.v2 import component
import streamlit as st


COPY_JS = """
export default function({ data, parentElement }) {
    const button = parentElement.querySelector('button');
    const status = parentElement.querySelector('[role="status"]');
    const fallback = parentElement.querySelector('textarea');
    button.textContent = data.label;
    fallback.value = data.text;
    button.onclick = async () => {
        try {
            await navigator.clipboard.writeText(data.text);
            fallback.hidden = true;
            status.textContent = 'Copied! Paste into your email or chat.';
        } catch {
            fallback.hidden = false;
            fallback.focus();
            fallback.select();
            status.textContent = 'Clipboard access is blocked. Press Ctrl+C (Command+C on Mac) to copy the selected text below.';
        }
    };
    return () => { button.onclick = null; };
}
"""

_COPY_ASSETS = dict(
    html='''<button type="button">Copy all analysis</button>
        <p role="status" aria-live="polite"></p>
        <textarea aria-label="Analysis text to copy" readonly hidden></textarea>''',
    css='''button {
        font: inherit; color: var(--st-text-color); background: var(--st-background-color);
        border: 1px solid var(--st-border-color, #999); border-radius: 8px;
        padding: 0.5rem 1rem; cursor: pointer;
    }
    button:hover { border-color: var(--st-primary-color); }
    p { font-size: 0.9rem; margin: 0.4rem 0; }
    p:empty { display: none; }
    textarea { box-sizing: border-box; width: 100%; height: 220px;
        color: var(--st-text-color); background: var(--st-background-color); }''',
    js=COPY_JS,
)


def copy_button(text: str, *, key: str, label: str = 'Copy all analysis') -> None:
    # Analysis is passed as data, never interpolated into HTML or JavaScript.
    # Register in the current runtime, including after an app reload.
    _copy = component(f'analysis_clipboard_{key}', **_COPY_ASSETS)
    _copy(data={'text': text, 'label': label}, key=key)


def copy_menu(text: str, *, key: str, label: str) -> None:
    # A native control stays visible even if custom JavaScript cannot load.
    with st.popover(label, icon=':material/content_copy:'):
        copy_button(text, key=f'{key}_clipboard', label='Copy to clipboard')
        st.caption('Or click the text below, press Ctrl+A, then Ctrl+C (Command on Mac).')
        st.text_area('Text to share', value=text, height=240, key=f'{key}_text')
