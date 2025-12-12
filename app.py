import csv
import io
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Face Swap QA Checklist", layout="wide")

APP_TITLE = "Face Swap QA — One-Page Checklist (Auto PASS/FAIL)"
st.title(APP_TITLE)

# -----------------------------
# Core evaluation logic (priority order)
# -----------------------------
def evaluate(checks: dict) -> tuple[str, str]:
    # A) Input completeness
    if not (checks["a_source_provided"] and checks["a_target_provided"] and checks["a_output_provided"]):
        return "FAIL", "missing required image(s)"

    # B) Source sanity
    if not checks["b_source_face_clear"] or not checks["b_source_no_distortions"]:
        return "FAIL", "source identity not clear enough"

    # C) Target anchor verifiable
    if not checks["c_target_expression_readable"] or not checks["c_target_pose_readable"] or not checks["c_target_mouth_readable"]:
        return "FAIL", "target expression/pose not verifiable"

    # D) Identity preservation
    if not checks["d_output_identity_preserved"] or not checks["d_output_features_match"]:
        return "FAIL", "identity not preserved"

    # E) Target match (critical)
    if not checks["e_expression_match"]:
        return "FAIL", "expression mismatch (Target → Output)"
    if not checks["e_pose_match"]:
        return "FAIL", "head pose mismatch (Target → Output)"
    if not checks["e_mouth_match"]:
        return "FAIL", "mouth position mismatch (Target → Output)"

    # F) Photorealism & blend
    f_ok = all([
        checks["f_no_cutout_edges"],
        checks["f_no_warping"],
        checks["f_no_double_features"],
        checks["f_sharpness_consistent"],
        checks["f_lighting_consistent"],
    ])
    if not f_ok:
        return "FAIL", "visible artifacts / unrealistic blending"

    # G) Consistency
    if not checks["g_no_gender_body_mismatch"]:
        return "FAIL", "gender/body inconsistency"
    if not checks["g_skin_tone_matches"] or not checks["g_no_weird_tint"]:
        return "FAIL", "skin tone/lighting inconsistency"
    if not checks["g_hairline_natural"] or not checks["g_no_hair_overlap_weirdness"]:
        return "FAIL", "unnatural hair blending"

    # H) Anatomy & scene integrity
    if not checks["h_no_disfigured_limbs"] or not checks["h_no_extra_missing_limbs"] or not checks["h_no_background_glitch"]:
        return "FAIL", "anatomical artifact / logical inconsistency"

    return "PASS", ""

def verdict_line(result: str, primary_reason: str, notes: str) -> str:
    if result == "PASS":
        return "PASS — natural blend, Source identity preserved, Target expression/pose/mouth matched."
    base = f"FAIL — Primary: {primary_reason}."
    notes = (notes or "").strip()
    if notes:
        base += f" Notes: {notes}"
    return base

# -----------------------------
# Session state
# -----------------------------
if "log_rows" not in st.session_state:
    st.session_state.log_rows = []

# Defaults: speed-first (most boxes True), inputs False
DEFAULTS = {
    "a_source_provided": False,
    "a_target_provided": False,
    "a_output_provided": False,

    "b_source_face_clear": True,
    "b_source_no_distortions": True,

    "c_target_expression_readable": True,
    "c_target_pose_readable": True,
    "c_target_mouth_readable": True,

    "d_output_identity_preserved": True,
    "d_output_features_match": True,

    "e_expression_match": True,
    "e_pose_match": True,
    "e_mouth_match": True,

    "f_no_cutout_edges": True,
    "f_no_warping": True,
    "f_no_double_features": True,
    "f_sharpness_consistent": True,
    "f_lighting_consistent": True,

    "g_no_gender_body_mismatch": True,
    "g_skin_tone_matches": True,
    "g_no_weird_tint": True,
    "g_hairline_natural": True,
    "g_no_hair_overlap_weirdness": True,

    "h_no_disfigured_limbs": True,
    "h_no_extra_missing_limbs": True,
    "h_no_background_glitch": True,
}

def ensure_defaults():
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

ensure_defaults()

# -----------------------------
# Top metadata
# -----------------------------
m1, m2, m3 = st.columns([1, 1, 2])
with m1:
    job_id = st.text_input("Job / Asset ID", placeholder="e.g., FS_2025_12_11_001")
with m2:
    reviewer = st.text_input("Reviewer", placeholder="e.g., Liman")
with m3:
    notes = st.text_input("Notes (1–2 lines)", placeholder="Concrete issue notes (if FAIL).")

st.divider()

# -----------------------------
# Buttons
# -----------------------------
b1, b2, b3 = st.columns([1, 1, 3])
with b1:
    if st.button("Mark All OK"):
        for k in DEFAULTS:
            if k.startswith("a_"):
                continue  # keep input checks manual
            st.session_state[k] = True
with b2:
    if st.button("Reset"):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.toast("Reset done.", icon="🧹")

# -----------------------------
# Checklist UI
# -----------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("A) Input Completeness")
    st.checkbox("Source image provided", key="a_source_provided")
    st.checkbox("Target image provided", key="a_target_provided")
    st.checkbox("Output image provided", key="a_output_provided")

    st.subheader("B) Source Image Sanity (Source Only)")
    st.checkbox("Source face is clearly visible", key="b_source_face_clear")
    st.checkbox("No obvious distortions in Source that prevent identity reading", key="b_source_no_distortions")

    st.subheader("C) Target Anchor (Target Only — Must Preserve)")
    st.checkbox("Target expression is clearly readable", key="c_target_expression_readable")
    st.checkbox("Target head pose is clearly readable", key="c_target_pose_readable")
    st.checkbox("Target mouth position is clearly readable", key="c_target_mouth_readable")

    st.subheader("D) Identity Preservation (Source → Output)")
    st.checkbox("Output clearly preserves Source identity", key="d_output_identity_preserved")
    st.checkbox("Key facial structure/features match Source", key="d_output_features_match")

with right:
    st.subheader("E) Target Match (Target → Output) ✅ Critical")
    st.checkbox("Output expression matches Target", key="e_expression_match")
    st.checkbox("Output head pose matches Target", key="e_pose_match")
    st.checkbox("Output mouth position matches Target", key="e_mouth_match")

    st.subheader("F) Photorealism & Blend (Output Only)")
    st.checkbox("No visible face cutout edges / hard seams", key="f_no_cutout_edges")
    st.checkbox("No warping around jaw/cheeks/ears/eyes/teeth", key="f_no_warping")
    st.checkbox("No double-features (ghost teeth, extra eyes, duplicated nose)", key="f_no_double_features")
    st.checkbox("Face sharpness matches scene (not pasted/over-smoothed)", key="f_sharpness_consistent")
    st.checkbox("Lighting/shadows consistent with scene", key="f_lighting_consistent")

    st.subheader("G) Consistency (Output Logic)")
    st.checkbox("No obvious gender/body-type mismatch", key="g_no_gender_body_mismatch")
    st.checkbox("Face tone matches neck/body", key="g_skin_tone_matches")
    st.checkbox("No weird tint (gray/green/orange)", key="g_no_weird_tint")
    st.checkbox("Hairline looks natural", key="g_hairline_natural")
    st.checkbox("No unnatural hair overlap around temples/forehead", key="g_no_hair_overlap_weirdness")

    st.subheader("H) Anatomy & Scene Integrity")
    st.checkbox("No disfigured limbs/hands/fingers in Output", key="h_no_disfigured_limbs")
    st.checkbox("No missing/extra limbs or impossible geometry", key="h_no_extra_missing_limbs")
    st.checkbox("No background bending/glitching caused by swap", key="h_no_background_glitch")

# -----------------------------
# Compute result
# -----------------------------
checks = {k: bool(st.session_state[k]) for k in DEFAULTS.keys()}
result, primary_reason = evaluate(checks)
line = verdict_line(result, primary_reason, notes)

st.divider()
st.subheader("Result")

if result == "PASS":
    st.success("PASS ✅")
    st.write("Primary fail reason: (none)")
else:
    st.error("FAIL ❌")
    st.write(f"Primary fail reason: **{primary_reason}**")

st.code(line)

# -----------------------------
# Logging (in-memory session log) + CSV download
# -----------------------------
c1, c2, c3 = st.columns([1, 1, 2])

with c1:
    if st.button("Add to Session Log"):
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "job_id": job_id.strip(),
            "reviewer": reviewer.strip(),
            "result": result,
            "primary_fail_reason": primary_reason,
            "notes": notes.strip(),
        }
        for k in sorted(checks.keys()):
            row[k] = checks[k]
        st.session_state.log_rows.append(row)
        st.toast("Added to log.", icon="✅")

with c2:
    if st.button("Clear Session Log"):
        st.session_state.log_rows = []
        st.toast("Cleared.", icon="🗑️")

with c3:
    if st.session_state.log_rows:
        # Build CSV
        headers = list(st.session_state.log_rows[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for r in st.session_state.log_rows:
            writer.writerow(r)

        st.download_button(
            "Download CSV (Session Log)",
            data=output.getvalue().encode("utf-8"),
            file_name="faceswap_qa_session_log.csv",
            mime="text/csv",
        )
    else:
        st.caption("No session log rows yet. Click “Add to Session Log” after a review.")
