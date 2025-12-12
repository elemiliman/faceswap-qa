import csv
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_TITLE = "Face Swap QA — One-Page Checklist (Auto PASS/FAIL)"
DEFAULT_LOG_NAME = "faceswap_qa_log.csv"


FAIL_REASONS = [
    "missing required image(s)",
    "source identity not clear enough",
    "target expression/pose not verifiable",
    "identity not preserved",
    "expression mismatch (Target → Output)",
    "head pose mismatch (Target → Output)",
    "mouth position mismatch (Target → Output)",
    "visible artifacts / unrealistic blending",
    "gender/body inconsistency",
    "skin tone/lighting inconsistency",
    "unnatural hair blending",
    "anatomical artifact / logical inconsistency",
]


def evaluate(checks: dict):
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

    # E) Target match (critical, most specific)
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


def verdict_line(result: str, primary_reason: str, notes: str):
    if result == "PASS":
        return "PASS — natural blend, Source identity preserved, Target expression/pose/mouth matched."
    base = f"FAIL — Primary: {primary_reason}."
    notes = (notes or "").strip()
    if notes:
        base += f" Notes: {notes}"
    return base


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self._window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Improve resize behavior
        def _on_canvas_configure(event):
            canvas.itemconfig(self._window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel support
        def _on_mousewheel(event):
            # Windows / Mac
            delta = event.delta
            if delta == 0:
                return
            canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x820")
        self.minsize(900, 700)

        self.log_path = os.path.abspath(DEFAULT_LOG_NAME)

        self.vars = {}
        self._build_vars()
        self._build_ui()
        self._wire_traces()
        self.update_result()

    def _build_vars(self):
        # Metadata
        self.job_id_var = tk.StringVar(value="")
        self.reviewer_var = tk.StringVar(value="")
        self.notes_var = tk.StringVar(value="")

        # Checklist (BooleanVars)
        def bv(default=False):
            return tk.BooleanVar(value=default)

        # Start with everything "OK" = True for speed, but inputs off by default.
        self.vars = {
            # A) Inputs
            "a_source_provided": bv(False),
            "a_target_provided": bv(False),
            "a_output_provided": bv(False),

            # B) Source sanity
            "b_source_face_clear": bv(True),
            "b_source_no_distortions": bv(True),

            # C) Target anchor
            "c_target_expression_readable": bv(True),
            "c_target_pose_readable": bv(True),
            "c_target_mouth_readable": bv(True),

            # D) Identity
            "d_output_identity_preserved": bv(True),
            "d_output_features_match": bv(True),

            # E) Target match
            "e_expression_match": bv(True),
            "e_pose_match": bv(True),
            "e_mouth_match": bv(True),

            # F) Photorealism
            "f_no_cutout_edges": bv(True),
            "f_no_warping": bv(True),
            "f_no_double_features": bv(True),
            "f_sharpness_consistent": bv(True),
            "f_lighting_consistent": bv(True),

            # G) Consistency
            "g_no_gender_body_mismatch": bv(True),
            "g_skin_tone_matches": bv(True),
            "g_no_weird_tint": bv(True),
            "g_hairline_natural": bv(True),
            "g_no_hair_overlap_weirdness": bv(True),

            # H) Anatomy
            "h_no_disfigured_limbs": bv(True),
            "h_no_extra_missing_limbs": bv(True),
            "h_no_background_glitch": bv(True),
        }

    def _wire_traces(self):
        for k, v in self.vars.items():
            v.trace_add("write", lambda *_: self.update_result())
        self.notes_var.trace_add("write", lambda *_: self.update_result())

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Top bar
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 14, "bold")).pack(side="left")

        ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Save Row", command=self.save_row).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Copy Verdict", command=self.copy_verdict).pack(side="right")

        # Metadata
        meta = ttk.LabelFrame(self, text="Review Details", padding=10)
        meta.pack(fill="x", padx=10, pady=(0, 10))

        row1 = ttk.Frame(meta)
        row1.pack(fill="x")

        ttk.Label(row1, text="Job / Asset ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(row1, textvariable=self.job_id_var, width=28).grid(row=0, column=1, sticky="w", padx=(6, 18))

        ttk.Label(row1, text="Reviewer:").grid(row=0, column=2, sticky="w")
        ttk.Entry(row1, textvariable=self.reviewer_var, width=22).grid(row=0, column=3, sticky="w", padx=(6, 18))

        ttk.Label(row1, text="Log file:").grid(row=0, column=4, sticky="w")
        self.log_label = ttk.Label(row1, text=self.log_path)
        self.log_label.grid(row=0, column=5, sticky="w")

        row2 = ttk.Frame(meta)
        row2.pack(fill="x", pady=(8, 0))

        ttk.Label(row2, text="Notes (1–2 lines):").grid(row=0, column=0, sticky="w")
        ttk.Entry(row2, textvariable=self.notes_var, width=110).grid(row=0, column=1, sticky="w", padx=(6, 0))

        # Buttons row
        btns = ttk.Frame(self, padding=(10, 0, 10, 10))
        btns.pack(fill="x")

        ttk.Button(btns, text="Mark All OK", command=self.mark_all_ok).pack(side="left")
        ttk.Button(btns, text="Reset All", command=self.reset_all).pack(side="left", padx=(8, 0))

        # Result panel
        result_box = ttk.LabelFrame(self, text="Result", padding=10)
        result_box.pack(fill="x", padx=10, pady=(0, 10))

        self.result_big = ttk.Label(result_box, text="—", font=("Segoe UI", 16, "bold"))
        self.result_big.pack(anchor="w")

        self.reason_label = ttk.Label(result_box, text="", font=("Segoe UI", 11))
        self.reason_label.pack(anchor="w", pady=(4, 0))

        self.verdict_text = tk.Text(result_box, height=2, wrap="word")
        self.verdict_text.pack(fill="x", pady=(8, 0))
        self.verdict_text.configure(state="disabled")

        # Checklist (scrollable)
        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        body = scroll.scrollable_frame

        # Build sections
        self._section_a(body)
        self._section_b(body)
        self._section_c(body)
        self._section_d(body)
        self._section_e(body)
        self._section_f(body)
        self._section_g(body)
        self._section_h(body)

        # Footer
        foot = ttk.Frame(self, padding=10)
        foot.pack(fill="x")
        ttk.Label(foot, text="Tip: If something is wrong, just untick the relevant box — FAIL reason updates automatically.").pack(anchor="w")

    def _make_section(self, parent, title):
        lf = ttk.LabelFrame(parent, text=title, padding=10)
        lf.pack(fill="x", expand=True, pady=6)
        return lf

    def _check(self, parent, text, key):
        cb = ttk.Checkbutton(parent, text=text, variable=self.vars[key])
        cb.pack(anchor="w", pady=2)

    def _section_a(self, parent):
        lf = self._make_section(parent, "A) Input Completeness")
        self._check(lf, "Source image provided", "a_source_provided")
        self._check(lf, "Target image provided", "a_target_provided")
        self._check(lf, "Output image provided", "a_output_provided")

    def _section_b(self, parent):
        lf = self._make_section(parent, "B) Source Image Sanity (Source Only)")
        self._check(lf, "Source face is clearly visible", "b_source_face_clear")
        self._check(lf, "No obvious distortions in Source that prevent identity reading", "b_source_no_distortions")

    def _section_c(self, parent):
        lf = self._make_section(parent, "C) Target Anchor (Target Only — Must Preserve)")
        self._check(lf, "Target expression is clearly readable", "c_target_expression_readable")
        self._check(lf, "Target head pose is clearly readable", "c_target_pose_readable")
        self._check(lf, "Target mouth position is clearly readable", "c_target_mouth_readable")

    def _section_d(self, parent):
        lf = self._make_section(parent, "D) Identity Preservation (Source → Output)")
        self._check(lf, "Output clearly preserves Source identity", "d_output_identity_preserved")
        self._check(lf, "Key facial structure/features match Source", "d_output_features_match")

    def _section_e(self, parent):
        lf = self._make_section(parent, "E) Target Match (Target → Output) ✅ Critical")
        self._check(lf, "Output expression matches Target", "e_expression_match")
        self._check(lf, "Output head pose matches Target", "e_pose_match")
        self._check(lf, "Output mouth position matches Target", "e_mouth_match")

    def _section_f(self, parent):
        lf = self._make_section(parent, "F) Photorealism & Blend (Output Only)")
        self._check(lf, "No visible face cutout edges / hard seams", "f_no_cutout_edges")
        self._check(lf, "No warping around jaw/cheeks/ears/eyes/teeth", "f_no_warping")
        self._check(lf, "No double-features (ghost teeth, extra eyes, duplicated nose)", "f_no_double_features")
        self._check(lf, "Face sharpness matches scene (not pasted/over-smoothed)", "f_sharpness_consistent")
        self._check(lf, "Lighting/shadows consistent with scene", "f_lighting_consistent")

    def _section_g(self, parent):
        lf = self._make_section(parent, "G) Consistency (Output Logic)")
        self._check(lf, "No obvious gender/body-type mismatch", "g_no_gender_body_mismatch")
        self._check(lf, "Face tone matches neck/body", "g_skin_tone_matches")
        self._check(lf, "No weird tint (gray/green/orange)", "g_no_weird_tint")
        self._check(lf, "Hairline looks natural", "g_hairline_natural")
        self._check(lf, "No unnatural hair overlap around temples/forehead", "g_no_hair_overlap_weirdness")

    def _section_h(self, parent):
        lf = self._make_section(parent, "H) Anatomy & Scene Integrity")
        self._check(lf, "No disfigured limbs/hands/fingers in Output", "h_no_disfigured_limbs")
        self._check(lf, "No missing/extra limbs or impossible geometry", "h_no_extra_missing_limbs")
        self._check(lf, "No background bending/glitching caused by swap", "h_no_background_glitch")

    def get_checks(self):
        return {k: bool(v.get()) for k, v in self.vars.items()}

    def update_result(self):
        checks = self.get_checks()
        result, reason = evaluate(checks)

        # Update labels
        if result == "PASS":
            self.result_big.config(text="PASS ✅", foreground="#0a7a0a")
            self.reason_label.config(text="Primary fail reason: (none)", foreground="#0a7a0a")
        else:
            self.result_big.config(text="FAIL ❌", foreground="#b00020")
            self.reason_label.config(text=f"Primary fail reason: {reason}", foreground="#b00020")

        # Verdict line
        line = verdict_line(result, reason, self.notes_var.get())
        self.verdict_text.configure(state="normal")
        self.verdict_text.delete("1.0", "end")
        self.verdict_text.insert("1.0", line)
        self.verdict_text.configure(state="disabled")

    def copy_verdict(self):
        checks = self.get_checks()
        result, reason = evaluate(checks)
        line = verdict_line(result, reason, self.notes_var.get())
        self.clipboard_clear()
        self.clipboard_append(line)
        self.update()  # keeps clipboard on some systems
        messagebox.showinfo("Copied", "Verdict copied to clipboard.")

    def mark_all_ok(self):
        # Mark everything except inputs as OK (True). Inputs stay as-is.
        for k, var in self.vars.items():
            if k.startswith("a_"):
                continue
            var.set(True)

    def reset_all(self):
        if not messagebox.askyesno("Reset", "Reset all checkboxes and fields?"):
            return
        self.job_id_var.set("")
        self.reviewer_var.set("")
        self.notes_var.set("")

        # Inputs false, everything else true (fast default)
        for k, var in self.vars.items():
            if k.startswith("a_"):
                var.set(False)
            else:
                var.set(True)

    def save_row(self):
        checks = self.get_checks()
        result, reason = evaluate(checks)

        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "job_id": self.job_id_var.get().strip(),
            "reviewer": self.reviewer_var.get().strip(),
            "result": result,
            "primary_fail_reason": reason,
            "notes": self.notes_var.get().strip(),
        }

        # Include checklist booleans
        for k in sorted(checks.keys()):
            row[k] = checks[k]

        # Ensure folder exists
        try:
            self._append_csv(self.log_path, row)
            messagebox.showinfo("Saved", f"Saved row to:\n{self.log_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV:\n{e}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Export CSV Log As...",
            defaultextension=".csv",
            initialfile=os.path.basename(self.log_path),
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return

        # If current log exists, copy it; otherwise create a blank with headers.
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, "rb") as src, open(path, "wb") as dst:
                    dst.write(src.read())
            else:
                # Create with headers
                checks = self.get_checks()
                headers = ["timestamp", "job_id", "reviewer", "result", "primary_fail_reason", "notes"] + sorted(checks.keys())
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
            messagebox.showinfo("Exported", f"Exported CSV to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export CSV:\n{e}")

    @staticmethod
    def _append_csv(path, row: dict):
        file_exists = os.path.exists(path)

        # Determine headers
        headers = list(row.keys())

        # If file exists, keep its header order if possible
        if file_exists:
            try:
                with open(path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    existing_headers = next(reader, None)
                if existing_headers and set(existing_headers) == set(headers):
                    headers = existing_headers
            except Exception:
                # fall back to current headers
                pass

        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)


if __name__ == "__main__":
    app = App()
    app.mainloop()
