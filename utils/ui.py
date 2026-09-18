"""Shared presentation for the project workspace."""
from html import escape
import streamlit as st


def apply_styles():
    st.html('''<style>
    .stMainBlockContainer {padding-top: 2rem; padding-bottom: 3rem; max-width: 1680px;}
    h1, h2, h3 {letter-spacing: -0.025em;}
    h1 {font-size: 2rem !important;}
    h2 {font-size: 1.5rem !important;}
    h3 {font-size: 1.15rem !important;}
    [data-testid="stSidebar"] {border-right: 1px solid #d9e2ec;}
    [data-testid="stMetric"] {background: #fff; border: 1px solid #dce5ec;
        border-radius: 12px; padding: 16px 20px;}
    [data-testid="stMetricValue"] {font-size: 1.8rem; font-weight: 650;}
    [data-testid="stTabs"] [role="tablist"] {gap: 1rem; margin-bottom: 1.2rem;}
    [data-testid="stTabs"] [role="tab"] {padding: 0.7rem 0.2rem; font-weight: 600;}
    [data-testid="stExpander"] {background: #fff; border-radius: 10px;}
    [data-testid="stDataFrame"] {border: 1px solid #dce5ec; border-radius: 10px; overflow: hidden;}
    .st-key-assistant_panel {background: #fff; border: 1px solid #dce5ec;
        border-radius: 14px; padding: 18px;}
    .st-key-document_preview {background: #fff; border: 1px solid #dce5ec;
        border-radius: 14px; padding: clamp(18px, 3vw, 40px);}
    .workspace-hero {background: #fff; border: 1px solid #dce5ec; border-radius: 14px;
        padding: 24px 28px; margin: 0 0 20px; border-left: 4px solid #087f8c;}
    .workspace-hero h1 {margin: 5px 0 8px; padding: 0; overflow-wrap: anywhere;}
    .workspace-hero p {margin: 0; color: #52657a; max-width: 900px; overflow-wrap: anywhere;}
    .workspace-eyebrow {font-size: .72rem; letter-spacing: .13em; text-transform: uppercase;
        color: #08717c; font-weight: 750;}
    .workspace-brand {font-size: 1.3rem; font-weight: 750; letter-spacing: -.04em; padding: 10px 0;}
    button:focus-visible, a:focus-visible {outline: 3px solid #087f8c !important; outline-offset: 3px;}
    @media (max-width: 900px) {
        .stMainBlockContainer {padding-left: 1rem; padding-right: 1rem;}
        .workspace-hero {padding: 18px;}
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-assistant_panel) {
            flex-direction: column;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-assistant_panel)
            > [data-testid="stColumn"] {width: 100%; flex: 1 1 100%;}
    }
    </style>''')


def project_header(name: str, description: str):
    st.html(f'''<section class="workspace-hero">
        <div class="workspace-eyebrow">Requirements workspace</div>
        <h1>{escape(name)}</h1><p>{escape(description)}</p></section>''')
