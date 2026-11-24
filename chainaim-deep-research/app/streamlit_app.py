"""ChainAIM Research - local app (PR-9). No AI: it only extracts, organises and saves files.

Start it with ops\\run_app.ps1 (or the VS Code task "Research: open app"); it opens
http://127.0.0.1:8501 and is reachable from this computer only.
All logic lives in app/services.py (tested by `evals/run_evals.py --only app`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import services as svc  # noqa: E402

st.set_page_config(page_title="ChainAIM Research", layout="wide")

KB_CHOICES = {
    "Transcript (test KB)": str(svc.REPO / "Transcript"),
    "Main KB (config.yaml)": None,
}
if os.environ.get("CHAINAIM_APP_KB"):   # optional: open another KB folder first (also used by the evals)
    KB_CHOICES = {"Custom (CHAINAIM_APP_KB)": os.environ["CHAINAIM_APP_KB"], **KB_CHOICES}
STATUS_LABEL = {"ok": "OK", "check": "CHECK", "missing": "missing"}

# ---------------- sidebar: which KB ----------------
with st.sidebar:
    st.header("ChainAIM Research")
    kb_label = st.radio("Knowledge base", list(KB_CHOICES), key="kb")
    paths = svc.kb_paths(KB_CHOICES[kb_label])
    list_file = paths["kb_dir"] / "links.txt"
    st.caption(f"Folder: {paths['kb_dir']}")
    holder = svc.lock_holder()
    if holder:
        st.warning(f"A run is active (PID {holder}). Wait for it to finish.")
    st.caption("No AI is used here. Summaries come from you pasting a prompt into any AI.")

entries = svc.list_entries(paths)
min_chars = int(paths["min_summary_chars"])


def run_steps(steps, log_name: str) -> bool:
    """Run script steps under the shared lock, streaming output into the page."""
    if not svc.acquire_lock():
        st.error("Another run is active (scheduled task or VS Code task). Try again when it finishes.")
        return False
    ok = True
    box = st.empty()
    lines = []
    try:
        for args in steps:
            for line in svc.run_script(args, log_name=log_name):
                lines.append(line)
                box.code("\n".join(lines[-200:]), language="text")
                if line.startswith("EXIT ") and line != "EXIT 0":
                    ok = False
    finally:
        svc.release_lock()
    return ok


tab_add, tab_lib, tab_save, tab_runs = st.tabs(["Add links", "Library", "Save summary", "Runs & digest"])

# ---------------- Add links ----------------
with tab_add:
    st.subheader("Add links")
    st.write("YouTube, GitHub repo or account, arXiv paper, or web article. One per line.")
    text = st.text_area("Links", height=150, key="links_text")
    if st.button("Add and extract now", key="btn_extract", type="primary"):
        good, bad = svc.parse_links(text)
        if bad:
            st.warning("Not recognised (skipped): " + ", ".join(bad))
        if not good:
            st.error("No valid link to add.")
        else:
            added, present = svc.add_links(list_file, good)
            st.write(f"Added {len(added)} new, {len(present)} already in {list_file.name}.")
            if run_steps(svc.extraction_args(paths["kb_dir"], list_file), "app-addlink"):
                st.success("Done. Open the Library tab to copy the prompt.")
            else:
                st.error("Some items failed - see the output above (also saved in logs/).")

# ---------------- Library ----------------
with tab_lib:
    st.subheader(f"Library ({len(entries)} items)")
    c1, c2, c3 = st.columns([3, 2, 2])
    q = c1.text_input("Search title", key="lib_q").strip().lower()
    kinds = c2.multiselect("Type", sorted({e.kind for e in entries}), key="lib_kind")
    stats = c3.multiselect("Summary", ["OK", "CHECK", "missing"], key="lib_status")
    shown = [e for e in entries
             if (not q or q in e.title.lower() or q in e.key.lower())
             and (not kinds or e.kind in kinds)
             and (not stats or STATUS_LABEL[e.status] in stats)]
    st.dataframe(
        [{"Added": e.added, "Type": e.kind, "Title": e.title, "Summary": STATUS_LABEL[e.status], "Key": e.key}
         for e in shown],
        hide_index=True,
    )
    if shown:
        pick = st.selectbox("Open item", shown, format_func=lambda e: f"{e.title}  [{e.key}]", key="lib_pick")
        st.write(f"Source: {pick.url}")
        prompt = svc.read_text(pick.prompt)
        if prompt:
            st.write("**Prompt** - use the copy icon (top-right of the box), paste into any AI, then save "
                     "its answer in the 'Save summary' tab.")
            st.code(prompt[:4000] + ("\n... (download for the full prompt)" if len(prompt) > 4000 else ""),
                    language="markdown")
            st.download_button("Download full prompt", prompt, file_name=pick.prompt.name, key="dl_prompt")
        else:
            st.info("No prompt yet - run 'Add and extract now' or the nightly task.")
        if pick.full:
            st.download_button("Download extracted text", svc.read_text(pick.full),
                               file_name=pick.full.name, key="dl_full")
        summary = svc.read_text(pick.summary)
        if summary:
            with st.expander(f"Summary ({STATUS_LABEL[pick.status]})", expanded=pick.status == "check"):
                st.markdown(summary)
            st.download_button("Download summary", summary, file_name=pick.summary.name, key="dl_sum")

# ---------------- Save summary ----------------
with tab_save:
    st.subheader("Save an AI summary")
    if not entries:
        st.info("Nothing extracted yet.")
    else:
        order = sorted(entries, key=lambda e: (e.status == "ok", e.title.lower()))
        target = st.selectbox("For item", order, key="save_pick",
                              format_func=lambda e: f"[{STATUS_LABEL[e.status]}] {e.title}  [{e.key}]")
        st.caption(f"Will be saved as {target.summary}")
        answer = st.text_area("Paste the AI's answer here", height=300, key="save_text")
        force = st.checkbox("Save anyway (short or command-like text)", key="save_force")
        if target.summary.exists():
            st.caption("A summary already exists for this item - saving replaces it.")
        if st.button("Save summary", key="btn_save", type="primary"):
            saved, msg = svc.save_summary(target, answer, min_chars=min_chars, force=force)
            (st.success if saved else st.error)(msg)
            if saved:
                run_steps([svc.extraction_args(paths["kb_dir"], list_file)[1]], "app-index")

# ---------------- Runs & digest ----------------
with tab_runs:
    st.subheader("Weekly digest")
    dg = svc.latest_digest(paths)
    if st.button("Make digest now (last 7 days)", key="btn_digest"):
        if run_steps([svc.digest_args(paths["kb_dir"])], "app-digest"):
            dg = svc.latest_digest(paths)
    if dg:
        with st.expander(f"Latest: {dg.name}", expanded=True):
            st.markdown(svc.read_text(dg))
    else:
        st.info("No digest yet.")

    st.subheader("Scheduled tasks")
    tasks = svc.scheduled_tasks()
    if tasks:
        st.dataframe(tasks, hide_index=True)
        st.caption("LastTaskResult 0 = OK; 267011 = has not run yet.")
    else:
        st.info("No scheduled tasks found (or not on Windows). Register them with ops\\register_tasks.ps1.")

    st.subheader("Recent logs")
    logs = svc.recent_logs()
    if logs:
        lg = st.selectbox("Log", logs, format_func=lambda p: p.name, key="log_pick")
        st.code(svc.read_text(lg)[-6000:], language="text")
    else:
        st.info("No logs yet.")
