# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link is a hub that names no add-on: an add-on's tools reach the
# echo, the panel and the rules through what it declares (agentlink/hooks.py,
# the family declarations), never through a name written here. This fails
# when an add-on's tool name or module name appears anywhere under
# agentlink/, outside credit lines and the few places listed in KNOWN.
import os
import re
import unittest

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink")

# The add-ons' tool names with an underscore, from their data/tools.json and
# Tool(...) definitions (14 Nov 2026). Names without one ("fit", "setup",
# "slice") are plain words and not checked. The private add-on checks its
# own names in its own repository.
TOOLS = (
    # SafetyNet
    "app_recover", "history_checkpoint", "history_restore", "macro_approve", "macro_list", "macro_run",
    "macro_save", "macro_show", "macro_unapprove", "pref_history", "pref_rollback",
    # ScanRuler for FreeCAD
    "align_auto", "align_clear", "align_datum", "align_symmetry", "catalog_links", "catalog_part",
    "catalog_provenance", "deviation_align", "deviation_export", "deviation_hotspots", "deviation_measure",
    "deviation_open_reference", "deviation_set_target", "deviation_settings", "deviation_volume",
    "dimension_add", "dimension_remove", "dimension_set_basic", "dimension_set_limit", "element_construct",
    "element_fit", "element_fit_marked", "element_list", "element_remove", "element_rename",
    "element_set_visible", "element_to_document", "element_unlink", "export_csv", "fit_scan_export",
    "fit_scan_features", "fit_scan_measure", "fit_scan_setup", "flat_calibrate", "flat_curvature",
    "flat_detect_edges", "flat_dimension_add", "flat_edges", "flat_edit", "flat_export", "flat_fit",
    "flat_note_add", "flat_objects", "flat_open_image", "flat_profile", "flat_remove", "flat_render",
    "flat_report", "flat_set_alignment", "manual_check", "manual_plan", "manual_render", "mesh_apply_reduced",
    "mesh_cut", "mesh_cut_preview", "mesh_delete_marked", "mesh_discard", "mesh_discard_edited",
    "mesh_export", "mesh_fill_holes", "mesh_flip_normals", "mesh_inspect", "mesh_mirror", "mesh_offset",
    "mesh_parts", "mesh_reduce", "mesh_remove_islands", "mesh_smooth", "mesh_undo", "mesh_use_edited",
    "pack_plan", "pack_setup", "pack_write", "report_get", "scan_cloud", "scan_draft", "scan_fit_surface",
    "scan_heightmap", "scan_info", "scan_nearest", "scan_noise", "scan_open", "scan_outline", "scan_pattern",
    "scan_qa", "scan_query", "scan_scale", "scan_segment", "scan_thread", "section_cut", "section_fit",
    "section_get", "section_list", "section_remove", "section_to_sketch", "thickness_measure",
    "thickness_settings", "wear_diff", "wear_prewarp", "wear_rebuild", "wear_setup",
    # Texturizer
    "texture_check", "texture_prepare",
    # Tutor
    "tutor_point", "tutor_watch",
    # Workshop
    "gen_make", "gen_part",
    # Workshop Documents
    "drawing_exploded", "drawing_make", "library_pack", "patent_draft", "patent_figures",
    # Workshop Electronics
    "board_enclosure", "kicad_import", "pcb_order_package", "printed_channel",
    # Workshop Make
    "cut_check", "cut_export", "dfm_check", "fea_frame", "hw_embed", "hw_embed_list", "hw_hole", "hw_pauses",
    "hw_unembed", "mass_ballast", "mass_calibrate", "mass_properties", "mass_target", "mill_check",
    "mill_export", "part_review", "part_spec", "printer_add", "printer_list", "printer_pause", "printer_send",
    "printer_status", "printer_stop", "slice_open", "slice_read", "slice_with", "slicer_presets",
    "thread_cut", "thread_identify", "thread_lookup",
)

# Their package names (case ignored, so the display names too; ScanRuler
# alone is the upstream app Agent Link credits, not an add-on). AddonKit is
# retired: its old module names stay only in provenance lines of the copies
# that came from it.
MODULES = ("scanrulerfc", "safetynet", "texturizer", "workshop", r"workshop_[a-z]+", "home_code", "orcalink", "collab", r"agentlink_collab", "tutor", r"agentlink_tutor")

TOOL_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(TOOLS, key=len, reverse=True)) + r")\b")
MODULE_RE = re.compile(r"(?i)\b(" + "|".join(MODULES) + r")\b")

# Credit lines name the people and work an add-on builds on: allowed.
CREDIT_RE = re.compile(r"(?i)stefan hermann|cnc kitchen|credit")

# Places that still name an add-on's tool, each until the step that moves
# it ({file: names}). Shrink this; never grow it without a step to end it.
KNOWN = {
    # After a crash the watchdog asks the recovery tool by name, and that
    # call is free of the pinned document: to move behind a declaration.
    "supervise.py": {"app_recover"},
    "gui_link.py": {"app_recover"},
    # A batch that rolls back refuses a restore inside it: to become a
    # family declaration.
    "tools.py": {"history_restore"},
    # The Activity tab's "Save as macro": moves to SafetyNet's own panel
    # (GUI design, build step 7).
    "panel.py": {"macro_save"},
    # The mass owner's hook service is asked by its name (a stable service
    # contract, as "manual_maker" is), not its tool.
    "families/measure.py": {"mass_properties"},
}

class NoAddonNames(unittest.TestCase):
    def test_lists_compile(self):
        self.assertTrue(TOOL_RE.search("x part_review y"))
        self.assertFalse(TOOL_RE.search("core_part_reviewed"))
        self.assertTrue(MODULE_RE.search("needs SafetyNet"))

    def test_agentlink_names_no_addon(self):
        hits = []
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if not f.endswith((".py", ".md", ".json", ".txt", ".toml")):
                    continue
                p = os.path.join(root, f)
                rel = os.path.relpath(p, HERE).replace(os.sep, "/")
                allowed = KNOWN.get(rel, set())
                with open(p, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if CREDIT_RE.search(line):
                            continue
                        found = set(TOOL_RE.findall(line)) | set(MODULE_RE.findall(line))
                        found = {x for x in found if x not in allowed}
                        if found:
                            hits.append(f"{rel}:{i}: {', '.join(sorted(found))}")
        self.assertEqual(hits, [], "Agent Link names an add-on; declare it on the add-on's family instead")

    def test_known_still_needed(self):
        """A KNOWN entry whose name is gone from its file is taken out."""
        stale = []
        for rel, allowed in KNOWN.items():
            with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
                text = fh.read()
            stale += [f"{rel}: {n}" for n in allowed if n not in text]
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
