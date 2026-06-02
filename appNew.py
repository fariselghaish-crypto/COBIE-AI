"""
app.py
COBie Pipeline — Streamlit Web Application
IFC → AI Enrich → COBie → Validate → Export
"""

import os
import tempfile
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from pipeline.ifc_parser import parse_ifc, get_summary
from pipeline.ai_enricher import enrich_all
from pipeline.cobie_builder import build_cobie
from pipeline.validator import validate_cobie
from pipeline.exporter import export_xlsx

load_dotenv()

st.set_page_config(
    page_title="COBie Pipeline",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0a0d13; color: #e2e8f0; }
    [data-testid="stSidebar"] { background-color: #111520; border-right: 1px solid #1e2a3e; }
    h1, h2, h3 { color: #00c9a7 !important; font-family: 'IBM Plex Mono', monospace !important; }
    [data-testid="stMetric"] { background: #161c2a; border: 1px solid #1e2a3e; border-radius: 8px; padding: 16px; }
    [data-testid="stDataFrame"] { border: 1px solid #1e2a3e; border-radius: 8px; }
    .stButton > button { background: #00c9a7; color: #000; font-weight: 700; border: none; font-family: monospace; letter-spacing: 1px; }
    .stButton > button:hover { background: #009e83; }
    .stDownloadButton > button { background: transparent; border: 1px solid #00c9a7; color: #00c9a7; font-family: monospace; }
    .tag { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 700; font-family: monospace; margin: 2px; }
    .tag-green { background: #00c9a722; color: #00c9a7; border: 1px solid #00c9a744; }
    .tag-blue { background: #3b82f622; color: #3b82f6; border: 1px solid #3b82f644; }
    .tag-orange { background: #f59e0b22; color: #f59e0b; border: 1px solid #f59e0b44; }
    .status-pass { background: #00c9a711; border-left: 4px solid #00c9a7; padding: 12px 16px; border-radius: 4px; }
    .status-fail { background: #ef444411; border-left: 4px solid #ef4444; padding: 12px 16px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.markdown("## ⬡")
with col_title:
    st.markdown("# COBie Pipeline")
    st.markdown(
        '<span class="tag tag-green">ISO 19650</span>'
        '<span class="tag tag-blue">COBie UK 2012</span>'
        '<span class="tag tag-orange">Uniclass 2015</span>'
        '<span class="tag tag-blue">SFG20</span>',
        unsafe_allow_html=True
    )

st.divider()

with st.sidebar:
    st.markdown("### ⚙️ Settings")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Your OpenAI API key. On Streamlit Cloud, set as a secret."
        )

    riba_stage = st.selectbox(
        "RIBA Stage Gate",
        ["Stage 2", "Stage 3", "Stage 4", "Handover"],
        index=3,
        help="Validation completeness threshold based on RIBA stage"
    )

    st.divider()
    st.markdown("### 📋 Pipeline Stages")
    st.markdown("""
    1. **Ingest** — Parse IFC file
    2. **Enrich** — AI fills COBie fields
    3. **Create** — Build all COBie sheets
    4. **Validate** — ISO 19650 + COBie UK 2012
    5. **Export** — Download .xlsx
    """)

    st.divider()
    st.markdown("### ℹ️ About")
    st.caption(
        "Built with IFCOpenShell, OpenAI GPT, and Streamlit. "
        "Validates against COBie UK 2012, ISO 19650-2, Uniclass 2015, and SFG20."
    )

uploaded = st.file_uploader(
    "Upload IFC File",
    type=["ifc"],
    help="Upload an IFC 2x3 or IFC 4 file"
)

if not api_key:
    st.warning("⚠️ Enter your OpenAI API key in the sidebar to enable AI enrichment.")

run_col, _ = st.columns([2, 8])
with run_col:
    run = st.button(
        "▶ Run Pipeline",
        disabled=not uploaded or not api_key,
        use_container_width=True,
        type="primary"
    )

if run and uploaded and api_key:

    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.status("⬡ Stage 1 — Parsing IFC file…", expanded=True) as status:
        try:
            elements = parse_ifc(tmp_path)
            summary = get_summary(elements)
            status.update(
                label=f"✓ Stage 1 — Parsed {len(elements)} elements",
                state="complete",
                expanded=False
            )
            st.success(f"Found {len(elements)} elements across {len(summary)} types")
        except Exception as e:
            status.update(label=f"✗ Stage 1 failed: {e}", state="error")
            st.error(f"IFC parsing failed: {e}")
            st.stop()

    with st.expander("📊 Element Type Summary", expanded=False):
        sum_df = pd.DataFrame(
            list(summary.items()),
            columns=["Element Type", "Count"]
        ).sort_values("Count", ascending=False)
        st.dataframe(sum_df, use_container_width=True, hide_index=True)

    with st.status("⬡ Stage 2 — AI Enrichment…", expanded=True) as status:
        progress_bar = st.progress(0)
        progress_text = st.empty()
        enrich_log = []

        def on_progress(done, total, el_type):
            progress_bar.progress(done / total)
            progress_text.text(f"Enriching [{done}/{total}]: {el_type}")

        try:
            enrichments, enrich_log = enrich_all(elements, api_key, on_progress)
            progress_bar.empty()
            progress_text.empty()
            unique_types = len({e["type"] for e in elements})
            status.update(
                label=f"✓ Stage 2 — Enriched {unique_types} element types",
                state="complete",
                expanded=False
            )
        except Exception as e:
            progress_bar.empty()
            progress_text.empty()
            status.update(label=f"✗ Stage 2 failed: {e}", state="error")
            st.error(f"AI enrichment failed: {e}")
            st.stop()

    with st.expander("🤖 AI Enrichment Log", expanded=False):
        for line in enrich_log:
            icon = "✅" if "AI" in line else "⚠️"
            st.text(f"{icon} {line}")

    with st.status("⬡ Stage 3 — Building COBie sheets…", expanded=True) as status:
        try:
            cobie = build_cobie(elements, enrichments)
            total_rows = sum(len(v) for v in cobie.values())
            status.update(
                label=f"✓ Stage 3 — {total_rows} rows across {len(cobie)} sheets",
                state="complete",
                expanded=False
            )
        except Exception as e:
            status.update(label=f"✗ Stage 3 failed: {e}", state="error")
            st.error(f"COBie build failed: {e}")
            st.stop()

    with st.status("⬡ Stage 4 — Validating…", expanded=True) as status:
        try:
            result = validate_cobie(cobie, riba_stage)
            label = (
                f"✓ Stage 4 — "
                f"{result['critical']} critical · "
                f"{result['warnings']} warnings · "
                f"{result['info']} info"
            )
            status.update(label=label, state="complete", expanded=False)
        except Exception as e:
            status.update(label=f"✗ Stage 4 failed: {e}", state="error")
            st.error(f"Validation failed: {e}")
            st.stop()

    with st.status("⬡ Stage 5 — Preparing export…", expanded=True) as status:
        try:
            xlsx_bytes = export_xlsx(cobie)
            status.update(label="✓ Stage 5 — Export ready", state="complete", expanded=False)
        except Exception as e:
            status.update(label=f"✗ Stage 5 failed: {e}", state="error")
            st.error(f"Export failed: {e}")
            st.stop()

    os.unlink(tmp_path)

    st.divider()

    tab_cobie, tab_val, tab_log = st.tabs([
        "📋 COBie Sheets",
        "✅ Validation Report",
        "📜 Log",
    ])

    with tab_cobie:
        st.download_button(
            label="⬇ Download COBie .xlsx",
            data=xlsx_bytes,
            file_name=f"COBie_{uploaded.name.replace('.ifc', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.markdown("---")
        sheet_order = [
            "Contact", "Facility", "Floor", "Space", "Zone",
            "Type", "Component", "System", "Document", "Job", "Resource", "Spare"
        ]

        for name in sheet_order:
            if name in cobie and not cobie[name].empty:
                with st.expander(
                    f"**{name}** — {len(cobie[name])} rows",
                    expanded=name in ["Component", "Type"]
                ):
                    st.dataframe(
                        cobie[name],
                        use_container_width=True,
                        hide_index=True
                    )

    with tab_val:
        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Critical",
            result["critical"],
            delta="Must fix" if result["critical"] > 0 else "None",
            delta_color="inverse"
        )
        m2.metric("Warnings", result["warnings"])
        m3.metric("Info", result["info"])
        m4.metric("Completeness", f"{result['completeness']:.0%}")

        if result["pass"]:
            st.markdown(
                '<div class="status-pass">✓ <strong>VALIDATION PASSED</strong> — '
                f'No critical issues for {riba_stage}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div class="status-fail">✗ <strong>VALIDATION FAILED</strong> — '
                f'{result["critical"]} critical issues must be resolved</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        if not result["issues"].empty:
            severity_filter = st.multiselect(
                "Filter by severity",
                ["CRITICAL", "WARNING", "INFO"],
                default=["CRITICAL", "WARNING"]
            )

            filtered = result["issues"][
                result["issues"]["Severity"].isin(severity_filter)
            ]

            # Plain dataframe only.
            # No Pandas styling is used, so the table cannot fail.
            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.success("No issues found — COBie is fully compliant.")

        st.markdown("---")
        st.markdown("**Standards checked:**")
        st.markdown(
            '<span class="tag tag-green">COBie UK 2012 — Mandatory fields</span>'
            '<span class="tag tag-green">COBie UK 2012 — Mandatory sheets</span>'
            '<span class="tag tag-blue">ISO 19650-2 — Naming convention</span>'
            '<span class="tag tag-orange">Uniclass 2015 — Classification</span>'
            '<span class="tag tag-blue">SFG20 — Maintenance coverage</span>'
            f'<span class="tag tag-green">RIBA {riba_stage} — Completeness gate</span>',
            unsafe_allow_html=True
        )

    with tab_log:
        st.code("\n".join(enrich_log), language="text")
