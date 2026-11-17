# SPDX-License-Identifier: LGPL-2.1-or-later
# The agent's work, shown as it happens in the FreeCAD window — as the
# ScanRuler fork shows it in the browser: for each call the workbench it
# belongs to comes up, the toolbar button that does the same job lights,
# what it works on is selected, a caption on the 3D view says what is being
# done, and afterwards what it made is selected and the body made active.
# Every call goes into an activity list (the Agent Link panel's Activity
# tab). Paced so the person can follow (Mod/AgentLink EchoDelay, ms;
# Echo off for none), and never in the way of the result: a failure here is
# logged, the call goes on.

import datetime
import time

try:
    import FreeCAD
except ImportError:  # the tables below are read without FreeCAD (tests)
    FreeCAD = None

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"

# Tool families → the workbench a person would be in.
WORKBENCH = [
    ("pd_", "PartDesignWorkbench"), ("sketch_", "SketcherWorkbench"), ("feature_", "PartDesignWorkbench"),
    ("part_", "PartWorkbench"), ("bim_", "BIMWorkbench"), ("ifc_", "BIMWorkbench"), ("fea_", "FemWorkbench"),
    ("td_", "TechDrawWorkbench"), ("draft_", "DraftWorkbench"),
    ("asm_", "AssemblyWorkbench"), ("cam_", "CAMWorkbench"), ("meshobj_", "MeshWorkbench"),
    ("sheet_", "SpreadsheetWorkbench"), ("insp_", "InspectionWorkbench"), ("points_", "PointsWorkbench"),
    ("surface_", "SurfaceWorkbench"), ("robot_", "RobotWorkbench"), ("scad_", "OpenSCADWorkbench"),
    ("material_", "MaterialWorkbench"),
]
# Tools that work on a drawing page: the page opens in its tab and the 3D
# view is not reframed after them.
PAGES = ["td_"]

# Tools → the FreeCAD command whose button does the same job.
COMMAND = {
    # sketch_new brings up the Sketcher, whose own New Sketch button lights
    # (Part Design's is inside its sketch dropdown, on another bench).
    "pd_body_new": "PartDesign_Body", "sketch_new": "Sketcher_NewSketch", "pd_pad": "PartDesign_Pad",
    "pd_pocket": "PartDesign_Pocket", "pd_revolution": "PartDesign_Revolution", "pd_groove": "PartDesign_Groove",
    "pd_hole": "PartDesign_Hole", "pd_fillet": "PartDesign_Fillet", "pd_chamfer": "PartDesign_Chamfer",
    "pd_draft": "PartDesign_Draft", "pd_thickness": "PartDesign_Thickness", "pd_mirrored": "PartDesign_Mirrored",
    "pd_linear_pattern": "PartDesign_LinearPattern", "pd_polar_pattern": "PartDesign_PolarPattern",
    "pd_multitransform": "PartDesign_MultiTransform", "pd_loft": "PartDesign_AdditiveLoft", "pd_pipe": "PartDesign_AdditivePipe",
    "pd_helix": "PartDesign_AdditiveHelix", "pd_boolean": "PartDesign_Boolean",
    # Datums: FreeCAD 1.1.3's Part Design toolbars have no PartDesign_Plane
    # button; the datum buttons on screen are Part's (the Part_Datums dropdown
    # every bench gets on its Structure toolbar: src/Mod/Part/Gui/
    # WorkbenchManipulator.cpp, src/Mod/PartDesign/Gui/Workbench.cpp).
    "pd_datum_plane": "Part_DatumPlane",
    # pd_binder makes a PartDesign::SubShapeBinder (agentlink/data/tools.json).
    "pd_binder": "PartDesign_SubShapeBinder", "pd_primitive": "PartDesign_CompPrimitiveAdditive",
    "pd_clone": "PartDesign_Clone", "pd_gear": "PartDesign_InvoluteGear", "pd_shaft": "PartDesign_WizardShaft",
    "pd_move_feature": "PartDesign_MoveFeature", "pd_reorder": "PartDesign_MoveFeatureInTree", "pd_tip": "PartDesign_MoveTip",
    # feature_edit: what a double-click on the feature runs. feature_suppress:
    # FreeCAD 1.1 has no command for it (a tick in the feature's own menu).
    "feature_edit": "Std_Edit",
    # Sketcher (FreeCAD 1.1: src/Mod/Sketcher/Gui/Command*.cpp). sketch_add,
    # sketch_constrain, sketch_edit, sketch_copy and sketch_bspline go by
    # what was asked for (command_for).
    # (FreeCAD 1.1.3 toolbars: src/Mod/Sketcher/Gui/Workbench.cpp. Projection
    # is inside the external-geometry dropdown, Sketcher_CompExternal; the
    # map, validate, merge and mirror buttons are on the Sketcher toolbar.)
    "sketch_offset": "Sketcher_Offset", "sketch_carbon": "Sketcher_CarbonCopy",
    "sketch_project": "Sketcher_Projection", "sketch_external": "Sketcher_Projection", "sketch_extend": "Sketcher_Extend",
    "sketch_join": "Sketcher_JoinCurves", "sketch_mirror": "Sketcher_MirrorSketch", "sketch_merge": "Sketcher_MergeSketches",
    "sketch_validate": "Sketcher_ValidateSketch", "sketch_to_bspline": "Sketcher_BSplineConvertToNURBS",
    "sketch_attach": "Sketcher_MapSketch", "sketch_copy": "Sketcher_Translate",
    "part_primitive": "Part_Primitives", "part_boolean": "Part_Boolean", "part_fillet": "Part_Fillet",
    "part_chamfer": "Part_Chamfer", "part_extrude": "Part_Extrude", "part_revolve": "Part_Revolve",
    "part_loft": "Part_Loft", "part_sweep": "Part_Sweep", "part_offset": "Part_Offset", "part_thickness": "Part_Thickness",
    "part_section": "Part_Section", "part_mirror": "Part_Mirror", "part_compound": "Part_Compound",
    # BIM's makers kept their Arch_ command names (FreeCAD 1.1: src/Mod/BIM/bimcommands).
    "bim_wall": "Arch_Wall", "bim_structure": "Arch_Structure", "bim_roof": "Arch_Roof", "bim_stairs": "Arch_Stairs",
    "bim_opening": "Arch_Window", "bim_space": "Arch_Space", "bim_level": "Arch_Level",
    "fea_setup": "FEM_Analysis", "fea_hold": "FEM_ConstraintFixed", "fea_load": "FEM_ConstraintForce",
    "fea_solve": "FEM_SolverRun", "fea_native": "FEM_Analysis",
    "td_page": "TechDraw_PageDefault", "td_view": "TechDraw_View", "td_projection": "TechDraw_ProjectionGroup",
    "td_section": "TechDraw_SectionView", "td_detail": "TechDraw_DetailView", "td_dim": "TechDraw_LengthDimension",
    "draft_text": "Draft_Text", "draft_array": "Draft_OrthoArray", "draft_clone": "Draft_Clone",
    "draft_dimension": "Draft_Dimension", "draft_label": "Draft_Label",
    "asm_new": "Assembly_CreateAssembly", "asm_add": "Assembly_InsertLink", "asm_joint": "Assembly_CreateJointFixed",
    "asm_explode": "Assembly_CreateView", "asm_bom": "Assembly_CreateBom",
    "cam_job": "CAM_Job", "cam_post": "CAM_Post", "cam_sim": "CAM_SimulatorGL",
    "measure": "Std_Measure", "section": "Part_Section", "doc_save": "Std_Save", "export_file": "Std_Export", "export": "Std_Export",
    "history_undo": "Std_Undo", "history_redo": "Std_Redo", "recompute": "Std_Refresh",
}

COMMAND.update({
    "asm_ground": "Assembly_ToggleGrounded", "asm_sub": "Assembly_InsertLink", "asm_new_part": "Assembly_InsertNewPart",
    # asm_motion keeps its own saved motions, not FreeCAD's Simulation: no button.
    "bim_building": "Arch_Building", "bim_section": "Arch_SectionPlane", "bim_grid": "Arch_AxisSystem", "bim_member": "BIM_Beam",
    "bim_frame": "Arch_Frame", "bim_equipment": "Arch_Equipment", "bim_panel": "Arch_Panel", "bim_rebar": "Arch_Rebar",
    "bim_truss": "Arch_Truss", "bim_curtain_wall": "Arch_CurtainWall", "bim_fence": "Arch_Fence", "bim_pipe": "Arch_Pipe",
    # bim_covering: FreeCAD 1.1 has no covering command.
    "bim_schedule": "Arch_Schedule", "bim_material": "BIM_Material",
    "cam_tool": "CAM_ToolController", "cam_tool_add": "CAM_ToolBitDock", "cam_setup": "CAM_Job",
})

# Round 4: the rest of the families, each tool to the button on its
# workbench's toolbar (FreeCAD 1.1.3: src/Mod/*/Gui/Workbench.cpp
# setupToolBars, the InitGui.py appendToolbar lists, src/Gui/Workbench.cpp's
# Std toolbars), or to a command inside a toolbar dropdown (Part's compound,
# split, join and offset groups, Std_LinkActions, TechDraw's groups: the
# dropdown's button lights). Only names in
# docs/hardening/freecad-1.1.0-commands.txt (tests/test_echo_rings.py). A
# tool with no button on any toolbar is left out: its call lights nothing and
# its trace says "no button".
COMMAND.update({
    # Mesh: Mesh Tools / Modify / Boolean / Cutting / Segmentation / Analyze
    # (src/Mod/Mesh/Gui/Workbench.cpp 239-293); MeshPart's unwrap is in the
    # menu only.
    "meshobj_smooth": "Mesh_Smoothing", "meshobj_decimate": "Mesh_Decimating", "meshobj_transform": "Mesh_Scale",
    "meshobj_offset": "Mesh_Scale", "meshobj_boolean": "Mesh_Union", "meshobj_sections": "Mesh_CrossSections",
    "meshobj_trim": "Mesh_TrimByPlane", "meshobj_merge": "Mesh_Merge", "meshobj_split": "Mesh_SplitComponents",
    "meshobj_segments": "Mesh_Segmentation", "meshobj_curvature": "Mesh_VertexCurvature", "meshobj_info": "Mesh_Evaluation",
    "meshobj_repair": "Mesh_HarmonizeNormals", "meshobj_primitive": "Mesh_BuildRegularSolid", "meshobj_from_shape": "Mesh_FromPartShape",
    "meshobj_export": "Mesh_Export", "meshobj_boundary": "Mesh_Evaluation", "meshobj_refine": "Mesh_RemeshGmsh",
    "meshobj_unwrap": "MeshPart_CreateFlatMesh", "meshobj_project": "MeshPart_CurveOnMesh", "meshobj_edit": "Mesh_AddFacet",
    # Surface toolbar (src/Mod/Surface/Gui/Workbench.cpp 63-77); sew, thicken,
    # loft and the fits light the Part button that does that job.
    "surface_boundary": "Surface_GeomFillSurface", "surface_fill": "Surface_Filling", "surface_sections": "Surface_Sections",
    "surface_extend": "Surface_ExtendFace", "surface_blend": "Surface_BlendCurve", "surface_cut": "Surface_Cut",
    "surface_loft": "Part_Loft", "surface_thicken": "Part_Thickness", "surface_sew": "Part_Builder",
    # The fits are Reverse Engineering's (its toolbar holds the surface fit;
    # the polynomial fit is in its menu only).
    "surface_points": "Reen_ApproxSurface", "surface_polynomial": "Reen_ApproxPolynomial",
    # Points Tools (src/Mod/Points/Gui/Workbench.cpp 46-58); the fits and the
    # mesh are Reverse Engineering's (its own toolbar, when loaded).
    "points_sample": "Points_Convert", "points_import": "Points_Import", "points_export": "Points_Export",
    "points_structure": "Points_Structure", "points_merge": "Points_Merge", "points_crop": "Points_PolyCut",
    "points_fit": "Reen_ApproxPlane", "points_mesh": "Reen_PoissonReconstruction", "points_info": "Points_Convert",
    # Spreadsheet toolbar (src/Mod/Spreadsheet/Gui/Workbench.cpp 238-264).
    "sheet_new": "Spreadsheet_CreateSheet", "sheet_import": "Spreadsheet_Import", "sheet_export": "Spreadsheet_Export",
    # Round 6: sheet_set, sheet_rows, sheet_clear, param_set, param_remove
    # light none — typing in cells, inserting rows and clearing are the
    # sheet's own keys and context menu, no toolbar button; the Alias
    # button they lit (sheet 0007-0055) is for another job.
    "sheet_cells": "Spreadsheet_MergeCells", "sheet_format": "Spreadsheet_StyleBold",
    "sheet_table": "Spreadsheet_CreateSheet", "param_bind": "Std_Expressions",
    "varset_new": "Std_VarSet", "varset_set": "Std_VarSet",
    # Part: Solids, Part Tools, Boolean Tools (src/Mod/Part/Gui/Workbench.cpp
    # 170-220) and their dropdowns (Part_CompCompoundTools,
    # Part_CompJoinFeatures, Part_CompSplitFeatures, Part_CompOffset).
    "part_face": "Part_MakeFace", "part_ruled": "Part_RuledSurface", "part_project": "Part_ProjectionOnSurface",
    "part_slices": "Part_CrossSections", "part_offset2d": "Part_Offset2D", "part_split": "Part_Slice",
    "part_refine": "Part_RefineShape", "part_defeature": "Part_Defeaturing", "part_container": "Std_Part",
    "part_join": "Part_JoinConnect", "part_extract": "Part_Builder", "part_fix": "Part_Builder",
    "part_from_mesh": "Part_ShapeFromMesh", "part_wire": "Part_Primitives", "part_transform": "Std_Placement",
    "part_attach": "Part_EditAttachment", "part_datum": "Part_DatumPlane", "part_import_curves": "Std_Import",
    "compound_filter": "Part_CompoundFilter", "compound_explode": "Part_ExplodeCompound",
    # BIM's toolbars (src/Mod/BIM/InitGui.py 74-256, 405-421): the 3D/BIM,
    # Annotation, Object, Manage and Utils lists.
    "bim_structure": "BIM_Slab", "bim_profiles": "Arch_Profile", "bim_component": "Arch_Component",
    "bim_edit": "Arch_Add", "bim_pipe_connector": "Arch_PipeConnector", "bim_structural_system": "Arch_StructuralSystem",
    "bim_quantities": "BIM_IfcQuantities", "bim_preflight": "BIM_Preflight", "bim_ifc": "BIM_IfcProperties",
    "bim_ifc_brep": "Arch_ToggleIfcBrepFlag", "bim_trash": "BIM_Trash", "bim_views": "BIM_Shape2DView",
    "bim_panel_out": "Arch_Panel_Cut", "bim_layers": "Arch_MultiMaterial", "bim_reorder": "BIM_Reorder",
    "bim_rewire": "BIM_Rewire", "bim_glue": "BIM_Glue", "bim_reextrude": "BIM_Reextrude", "bim_image_plane": "BIM_ImagePlane",
    "bim_remove_shape": "Arch_RemoveShape", "bim_library": "BIM_Library", "bim_reference": "Arch_Reference",
    "bim_nest": "Arch_Nest", "bim_list": "BIM_Views", "bim_export": "Std_Export", "bim_import": "Std_Import",
    "ifc_diff": "BIM_Diff", "ifc_save": "Std_Save", "ifc_open": "Std_Open", "ifc_edit": "BIM_IfcProperties",
    "ifc_find": "BIM_IfcExplorer", "ifc_remove": "Std_Delete",
    # Draft (src/Mod/Draft/draftutils/init_tools.py): creation, annotation,
    # modification and utility toolbars.
    "draft_shape": "Draft_Wire", "draft_modify": "Draft_Move", "draft_link_array": "Draft_OrthoArray",
    "draft_facebinder": "Draft_Facebinder", "draft_hatch": "Draft_Hatch", "draft_layer": "Draft_Layer",
    "draft_style": "Draft_AnnotationStyleEditor", "draft_to_sketch": "Draft_Draft2Sketch", "draft_from_sketch": "Draft_Draft2Sketch",
    "draft_fix": "Draft_FlipDimension", "draft_plane": "Draft_SelectPlane", "draft_2d_view": "Draft_Shape2DView",
    "draft_outline": "Draft_ShapeString",
    # TechDraw (src/Mod/TechDraw/Gui/Workbench.cpp setupToolBars).
    "td_note": "TechDraw_Annotation", "td_leader": "TechDraw_LeaderLine", "td_balloon": "TechDraw_Balloon",
    "td_weld": "TechDraw_WeldSymbol", "td_finish": "TechDraw_SurfaceFinishSymbols", "td_tolerance": "TechDraw_HoleShaftFit",
    "td_hatch": "TechDraw_Hatch", "td_title": "TechDraw_FillTemplateFields", "td_export": "TechDraw_ExportPageSVG",
    "td_centermarks": "TechDraw_ExtensionCircleCenterLines", "td_cosmetic": "TechDraw_2PointCosmeticLine",
    "td_dimset": "TechDraw_ExtensionCreateHorizChainDimension", "td_dim_special": "TechDraw_HorizontalExtentDimension",
    "td_dim_repair": "TechDraw_DimensionRepair", "td_dim_format": "TechDraw_ExtensionCustomizeFormat",
    "td_dim_align": "TechDraw_ExtensionPosHorizChainDimension", "td_lines": "TechDraw_ExtensionChangeLineAttributes",
    "td_section_position": "TechDraw_ExtensionPositionSectionView", "td_view_more": "TechDraw_ExtensionLockUnlockView",
    "td_area": "TechDraw_AreaDimension", "td_datum": "TechDraw_LeaderLine", "td_gdt": "TechDraw_RichTextAnnotation",
    "td_table": "TechDraw_SpreadsheetView", "td_bim": "TechDraw_ArchView",
    # CAM (src/Mod/CAM/InitGui.py 127-269).
    "cam_edit": "CAM_OpActiveToggle", "cam_path": "CAM_Area", "cam_property_bag": "CAM_PropertyBag",
    "cam_template_export": "CAM_ExportTemplate", "cam_remove": "Std_Delete", "cam_library": "CAM_ToolBitDock",
    # FEM (src/Mod/Fem/Gui/Workbench.cpp setupToolBars).
    "fea_refine": "FEM_MeshRegion", "fea_shell": "FEM_ElementGeometry2D", "fea_heat": "FEM_ConstraintTemperature",
    "fea_modes": "FEM_SolverRun", "fea_buckle": "FEM_SolverRun", "fea_parts": "FEM_ConstraintTie",
    "fea_clear": "FEM_ResultsPurge", "fem_mesh": "FEM_MeshNetgenFromShape", "fem_add": "FEM_ConstraintDisplacement",
    "fem_linearize": "FEM_PostFilterLinearizedStresses",
    # Inspection, OpenSCAD, Robot, Material.
    "insp_run": "Inspection_VisualInspection", "insp_update": "Inspection_VisualInspection",
    "scad_op": "OpenSCAD_Hull", "scad_code": "OpenSCAD_AddOpenSCADElement", "scad_tidy": "OpenSCAD_RefineShapeFeature",
    "scad_import": "Std_Import", "scad_export": "Std_Export",
    "robot_new": "Robot_Create", "robot_path": "Robot_CreateTrajectory", "robot_trajectory": "Robot_TrajectoryCompound",
    "robot_move": "Robot_RestoreHomePos", "robot_tool": "Robot_AddToolShape", "robot_export": "Robot_ExportKukaFull",
    "material_set": "Material_Edit", "material_clear": "Material_Edit",
    # The Std toolbars every bench has (src/Gui/Workbench.cpp 830-885):
    # File, Edit, View and Structure (Std_LinkActions holds the link
    # commands).
    "doc_new": "Std_New", "doc_open": "Std_Open", "doc_save_all": "Std_Save", "doc_revert": "Std_Open",
    "doc_close": "Std_CloseActiveWindow", "doc_info": "Std_ProjectInfo", "doc_graph": "Std_DependencyGraph",
    "text_document": "Std_TextDocument",
    "doc_merge": "Std_Open", "object_group": "Std_Group", "link_make": "Std_LinkMake", "link_edit": "Std_LinkReplace",
    "object_set": "Std_Placement", "object_align": "Std_Placement", "object_duplicate": "Std_DuplicateSelection",
    "object_delete": "Std_Delete", "object_appearance": "Std_SetAppearance", "object_freeze": "Std_ToggleFreeze",
    "measure_keep": "Std_Measure", "measure_mass": "Std_Measure", "clearance": "Std_Measure", "import_file": "Std_Import",
    "asm_check": "Assembly_SolveAssembly", "asm_export": "Assembly_ExportASMT", "asm_motion": "Assembly_CreateSimulation",
})

# Tools whose button follows one argument: {tool: (argument, {its value,
# flattened (_flat): command})}. A value not listed takes COMMAND's.
BY_ARG = {
    "part_primitive": ("kind", {"box": "Part_Box", "cylinder": "Part_Cylinder", "sphere": "Part_Sphere", "cone": "Part_Cone",
                                "torus": "Part_Torus", "tube": "Part_Tube"}),
    "part_boolean": ("op", {"fuse": "Part_Fuse", "cut": "Part_Cut", "common": "Part_Common"}),
    "meshobj_boolean": ("op", {"union": "Mesh_Union", "fuse": "Mesh_Union", "intersection": "Mesh_Intersection",
                               "common": "Mesh_Intersection", "difference": "Mesh_Difference", "cut": "Mesh_Difference"}),
    "part_split": ("mode", {"slice": "Part_Slice", "fragments": "Part_BooleanFragments", "xor": "Part_XOR"}),
    "part_join": ("kind", {"connect": "Part_JoinConnect", "embed": "Part_JoinEmbed", "cutout": "Part_JoinCutout"}),
    "part_datum": ("kind", {"point": "Part_DatumPoint", "line": "Part_DatumLine", "plane": "Part_DatumPlane",
                            "csys": "Part_CoordinateSystem"}),
    "part_fix": ("op", {"reverse": "Part_ReverseShape", "solid": "Part_MakeSolid"}),
    "points_fit": ("shape", {"plane": "Reen_ApproxPlane", "cylinder": "Reen_ApproxCylinder", "sphere": "Reen_ApproxSphere",
                             "surface": "Reen_ApproxSurface", "curve": "Reen_ApproxCurve"}),
    "draft_shape": ("kind", {"line": "Draft_Line", "wire": "Draft_Wire", "polyline": "Draft_Wire", "circle": "Draft_Circle",
                             "arc": "Draft_Arc", "ellipse": "Draft_Ellipse", "rectangle": "Draft_Rectangle",
                             "polygon": "Draft_Polygon", "bspline": "Draft_BSpline", "bezier": "Draft_BezCurve",
                             "point": "Draft_Point"}),
    "draft_modify": ("op", {"move": "Draft_Move", "rotate": "Draft_Rotate", "scale": "Draft_Scale", "mirror": "Draft_Mirror",
                            "offset": "Draft_Offset", "upgrade": "Draft_Upgrade", "downgrade": "Draft_Downgrade",
                            "join": "Draft_Join", "fillet": "Draft_Fillet", "split": "Draft_Split",
                            "stretch": "Draft_Stretch", "trim": "Draft_Trimex", "extend": "Draft_Trimex"}),
    "draft_link_array": ("kind", {"ortho": "Draft_OrthoArray", "polar": "Draft_PolarArray", "circular": "Draft_CircularArray",
                                  "path": "Draft_PathLinkArray", "point": "Draft_PointLinkArray"}),
    "td_dimset": ("type", {"horizontal": "TechDraw_ExtensionCreateHorizChainDimension",
                           "vertical": "TechDraw_ExtensionCreateVertChainDimension"}),
    "td_dim_special": ("kind", {"extenth": "TechDraw_HorizontalExtentDimension", "extentv": "TechDraw_VerticalExtentDimension",
                                "chamferh": "TechDraw_ExtensionCreateHorizChamferDimension",
                                "chamferv": "TechDraw_ExtensionCreateVertChamferDimension",
                                "arclength": "TechDraw_ExtensionCreateLengthArc", "axolength": "TechDraw_AxoLengthDimension"}),
    "fea_hold": ("kind", {"fixed": "FEM_ConstraintFixed", "pin": "FEM_ConstraintFixed", "slide": "FEM_ConstraintDisplacement",
                          "move": "FEM_ConstraintDisplacement"}),
    "scad_op": ("op", {"hull": "OpenSCAD_Hull", "minkowski": "OpenSCAD_Minkowski"}),
}


def _by_arg(name, a):
    """The button BY_ARG gives for this call's argument, or None."""
    row = BY_ARG.get(name)
    if not row:
        return None
    key, table = row
    return table.get(_flat(a.get(key)))


def _fea_load_command(a):
    """fea_load: gravity on the self-weight button, pressure on Pressure,
    else Force (the old ring lit Force for gravity, fem 033)."""
    if a.get("gravity") not in (None, False):
        return "FEM_ConstraintSelfWeight"
    if a.get("pressure") is not None:
        return "FEM_ConstraintPressure"
    if a.get("temperature") is not None:
        return "FEM_ConstraintTemperature"
    return "FEM_ConstraintForce"

# Tools whose button depends on what kind was asked for.
CAM_OP = {"profile": "CAM_Profile", "pocket": "CAM_Pocket_Shape", "adaptive": "CAM_Adaptive", "face": "CAM_MillFace",
          "drill": "CAM_Drilling", "engrave": "CAM_Engrave", "helix": "CAM_Helix", "slot": "CAM_Slot", "deburr": "CAM_Deburr",
          "vcarve": "CAM_Vcarve", "thread": "CAM_ThreadMilling", "surface": "CAM_Surface", "waterline": "CAM_Waterline"}
# pd_datum's kinds (pd_datum_plane has its own entry above).
PD_DATUM = {"line": "Part_DatumLine", "point": "Part_DatumPoint", "lcs": "Part_CoordinateSystem"}
# Part Design tools that cut with subtractive: true: the cutting button.
PD_SUBTRACTIVE = {"pd_primitive": "PartDesign_CompPrimitiveSubtractive", "pd_loft": "PartDesign_SubtractiveLoft",
                  "pd_pipe": "PartDesign_SubtractivePipe", "pd_helix": "PartDesign_SubtractiveHelix"}
# sketch_add's kinds, sketch_constrain's types and sketch_edit's keys: the
# button a person would push for the first one asked for.
SKETCH_ADD = {"line": "Sketcher_CreateLine", "polyline": "Sketcher_CreatePolyline", "arc": "Sketcher_CreateArc",
              "arc3": "Sketcher_Create3PointArc", "circle": "Sketcher_CreateCircle", "circle3": "Sketcher_Create3PointCircle",
              "ellipse": "Sketcher_CreateEllipseByCenter", "parabola": "Sketcher_CreateArcOfParabola",
              "hyperbola": "Sketcher_CreateArcOfHyperbola", "bspline": "Sketcher_CreateBSpline",
              "rectangle": "Sketcher_CreateRectangle", "roundedrectangle": "Sketcher_CreateOblong",
              "polygon": "Sketcher_CreateRegularPolygon", "slot": "Sketcher_CreateSlot", "arcslot": "Sketcher_CreateArcSlot",
              "point": "Sketcher_CreatePoint"}
SKETCH_CONSTRAIN = {"coincident": "Sketcher_ConstrainCoincidentUnified", "pointonobject": "Sketcher_ConstrainCoincidentUnified",
                    "horizontal": "Sketcher_ConstrainHorizontal", "vertical": "Sketcher_ConstrainVertical",
                    "parallel": "Sketcher_ConstrainParallel", "perpendicular": "Sketcher_ConstrainPerpendicular",
                    "equal": "Sketcher_ConstrainEqual", "tangent": "Sketcher_ConstrainTangent",
                    "symmetric": "Sketcher_ConstrainSymmetric", "distance": "Sketcher_ConstrainDistance",
                    "distancex": "Sketcher_ConstrainDistanceX", "distancey": "Sketcher_ConstrainDistanceY",
                    "radius": "Sketcher_ConstrainRadius", "diameter": "Sketcher_ConstrainDiameter",
                    "angle": "Sketcher_ConstrainAngle", "fix": "Sketcher_ConstrainLock", "lock": "Sketcher_ConstrainLock",
                    "block": "Sketcher_ConstrainBlock"}
SKETCH_EDIT = (("fillet", "Sketcher_CreateFillet"), ("trim", "Sketcher_Trimming"), ("split", "Sketcher_Split"),
               ("mirror", "Sketcher_Symmetry"), ("construction", "Sketcher_ToggleConstruction"),
               ("set", "Sketcher_ChangeDimensionConstraint"), ("deleteConstraints", "Sketcher_DeleteAllConstraints"),
               ("removeAxesAlignment", "Sketcher_RemoveAxesAlignment"),
               ("exposeInternal", "Sketcher_RestoreInternalAlignmentGeometry"))


def _flat(word):
    return str(word or "").lower().replace("-", "").replace("_", "")


def _sketch_command(name, a):
    """The Sketcher button for a sketch tool that goes by what was asked."""
    if name == "sketch_add":
        first = next((it for it in a.get("items") or [] if isinstance(it, dict)), {}) if isinstance(a.get("items"), list) else {}
        return SKETCH_ADD.get(_flat(first.get("kind")))
    if name == "sketch_constrain":
        first = next((c for c in a.get("constraints") or [] if isinstance(c, dict)), {}) if isinstance(a.get("constraints"), list) else {}
        return SKETCH_CONSTRAIN.get(_flat(first.get("type") or first.get("kind")))
    if name == "sketch_edit":
        return next((cmd for key, cmd in SKETCH_EDIT if a.get(key)), None)
    if name == "sketch_copy":
        return "Sketcher_Rotate" if a.get("rotate") else "Sketcher_Scale" if a.get("scale") else "Sketcher_Translate"
    if name == "sketch_array":
        # FreeCAD 1.1 makes arrays with Move/Array and Rotate/Polar Transform
        # (their copies and rows); Sketcher_RectangularArray is on no toolbar.
        return "Sketcher_Rotate" if a.get("polar") else "Sketcher_Translate"
    if name == "sketch_bspline":
        down = isinstance(a.get("by"), (int, float)) and a["by"] < 0
        if _flat(a.get("op")) == "degree":
            return "Sketcher_BSplineDecreaseDegree" if down else "Sketcher_BSplineIncreaseDegree"
        if a.get("param") is not None:
            return "Sketcher_BSplineInsertKnot"
        return "Sketcher_BSplineDecreaseKnotMultiplicity" if down else "Sketcher_BSplineIncreaseKnotMultiplicity"
    return None


SKETCH_BY_ASK = ("sketch_add", "sketch_constrain", "sketch_edit", "sketch_copy", "sketch_array", "sketch_bspline")
CAM_DRESSUP = {"dogbone": "CAM_DressupDogbone", "tag": "CAM_DressupTag", "tags": "CAM_DressupTag", "ramp": "CAM_DressupRampEntry",
               "boundary": "CAM_DressupPathBoundary", "leadinout": "CAM_DressupLeadInOut", "axismap": "CAM_DressupAxisMap", "zcorrect": "CAM_DressupZCorrect"}


def command_for(name, args):
    """The command whose button does what this call does."""
    # An add-on's NO_BUTTON (exact name or prefix): no button, whatever matches.
    if _longest(name, ((k, True) for k in NO_BUTTON)):
        return None
    kind = str((args or {}).get("kind") or "").lower().replace("-", "").replace("_", "")
    if name == "asm_joint" and kind:
        return "Assembly_CreateJoint" + {"rackpinion": "RackPinion", "slider": "Slider", "ball": "Ball"}.get(kind, kind.capitalize())
    if name == "cam_op" and kind in CAM_OP:
        return CAM_OP[kind]
    if name == "cam_dressup" and kind in CAM_DRESSUP:
        return CAM_DRESSUP[kind]
    if name in SKETCH_BY_ASK:
        return _sketch_command(name, args or {})
    if name == "pd_datum":
        return PD_DATUM.get(kind)
    if name == "pd_tip" and not (args or {}).get("feature"):
        return None  # it only reads the tip
    if name in PD_SUBTRACTIVE and (args or {}).get("subtractive") is True:
        return PD_SUBTRACTIVE[name]
    if name == "fea_load":
        return _fea_load_command(args or {})
    got = _by_arg(name, args or {})
    if got:
        return got
    if name in COMMAND:
        return COMMAND[name]
    # What add-ons declared (declare()): their own callables first, then
    # COMMANDS by exact name or longest prefix.
    for fn in list(COMMAND_FNS):
        try:
            got = fn(name, args or {})
        except Exception:
            got = None
        if isinstance(got, str) and got:
            return got
    return _longest(name, COMMANDS.items())


# Add-ons' own buttons, declared on their family modules (declare()):
# {tool or prefix: command}, and command_for(name, args) callables.
COMMANDS = {}
COMMAND_FNS = []
# Tools (names or prefixes) whose calls light no button, even where a
# COMMANDS prefix would match them.
NO_BUTTON = set()


def _longest(name, pairs):
    """The value of the longest key that is name or a prefix of it."""
    best, got = -1, None
    for k, v in pairs:
        if isinstance(k, str) and name.startswith(k) and len(k) > best:
            best, got = len(k), v
    return got


# Tools never shown as they run (no bench, button, caption or selection;
# still listed in Activity): the server's own, and what add-ons declare as
# NO_ECHO (names or prefixes), such as tools that draw in the window
# themselves.
SKIP = {"batch", "session_state", "tool_groups", "guide_read"}
NO_ECHO = set()

# Tools that look at the window or the session and leave it as it is: a
# picture of the window, the Report view, the session's state. They show
# nothing of their own and put nothing out — the ring, the words and the
# selection of the last changing call stay as they were, so a picture taken
# right after a change shows that change (round 2 put the ring out at the
# start of every call, the snapshot's own too: no picture had a ring).
# Add-ons declare theirs as WATCH (names or prefixes).
WATCH = {"window_snapshot", "view_snapshot", "view_render", "view_maps", "snapshot_latest", "snapshot_list",
         "report_read", "usage_report", "job_status", "crash_collect", "steps_list", "note_list"}
# (doc_graph left the list in round 4: as a look it kept the last call's
# words, so its picture read "Read the document's details", core 0031; it is
# a read and says its own.)

# How long what the echo shows for a changing call stays: the lit button,
# the words over the 3D view and in the status bar. Until the next changing
# call's own echo puts them out, or this long with no call at all (a ring
# lit for 1.3 s and words for 2.6 s were gone before the picture of the
# call was taken whenever the call or the batch around it took longer).
HOLD_MS = 30000


def skipped(name):
    """Whether a call of this tool is left out of the echo."""
    return name in SKIP or bool(_longest(name, ((k, True) for k in NO_ECHO)))


def watching(name):
    """Whether a call of this tool only looks (WATCH): no echo of its own,
    and nothing of the last change's put out."""
    return isinstance(name, str) and (name in WATCH or bool(_longest(name, ((k, True) for k in WATCH if k.endswith("_")))))


# Read-only tools that still show something (a view, a picture).
SHOWN = ("view_", "measure", "clearance", "section", "body_check", "steps_render", "note_")
# Read-only tools that open a panel or dialog all the same, and so bring up
# their workbench (add-ons declare theirs as OPENS). Every other read leaves
# the bench as the person has it.
OPENS = ()


def switches_bench(tool):
    """Whether a call brings up its workbench: one that changes the document
    (its tool's changes flag, after for_call, so a changing tool's read
    action counts as a read) or opens a panel; a read never does."""
    if tool is None:
        return False
    return bool(getattr(tool, "changes", False)) or bool(OPENS) and tool.name.startswith(OPENS)

# What a tool's arguments and answer name: the objects to select.
ARG_KEYS = ("body", "sketch", "object", "base", "target", "feature", "page", "op", "joint")
OUT_KEYS = ("feature", "sketch", "object", "body", "created", "page", "view", "joint", "op", "sub",
            # Mesh, Surface, Draft, BIM and Spreadsheet answers name what
            # they made under these (meshobj keep/finish: "mesh"; the Mesh
            # Info panel stayed empty because no mesh was ever selected).
            "mesh", "surface", "layer", "projection", "sections", "pieces", "views", "made",
            # Round 4: links, text documents, trajectories, groups.
            "link", "text", "trajectory", "group")
# More of the same for single tools, where the answer (or, for a call that
# moves a thing, its arguments) names what was made or changed under a key
# of its own. A value is a name or a list of names.
OUT_MORE = {"pd_datum": ("datum",), "pd_datum_plane": ("plane",), "pd_binder": ("binder",), "pd_shaft": ("shaft",),
            "pd_move_feature": ("moved",), "pd_tip": ("tip",), "pd_reorder": ("feature",),
            "asm_add": ("added",), "asm_sub": ("as",), "asm_new_part": ("inAssembly", "part"), "asm_bom": ("sheet",),
            "asm_explode": ("view",), "asm_new": ("assembly",), "bim_material": ("on",), "draft_fix": ("object", "dimension"),
            "fea_parts": ("parts",), "meshobj_split": ("pieces",), "cam_dressup": ("dressup",),
            # bim_views: views [{ level, section, view }]; bim_panel_out:
            # cuts [{ panel, cut }] (bim 042, 048 showed the model from the
            # top, not the plan or the cut sheet).
            "bim_views": ("views",), "bim_panel_out": ("cuts", "sheet"),
            # Round 6: what object_appearance coloured ({ object } rows; core
            # 0032 selected nothing, so the copy lying on Block stayed opaque).
            "object_appearance": ("set",),
            # Round 6: the axes a grid made (bim 037).
            "bim_grid": ("axes",)}
# Tools whose own keys name the result alone when given (the answer's
# "object" is what they read, not what they made): a fit's new body, not the
# cloud (points 0011); a duplicate's copy (core 0025); the part grounded,
# not the joint that holds it (asm 032).
OUT_ONLY = {"points_fit": ("body",), "object_duplicate": ("duplicated",), "asm_ground": ("part",),
            "points_mesh": ("mesh",), "points_structure": ("points",), "points_merge": ("points",)}
# In an answer's list of rows ({ from, copy }), the keys that name what was
# made.
ROW_KEYS = ("copy", "made", "view", "cut", "object", "name")
# What a changing call made when its answer names nothing: the objects new
# in the document since before it, at most NEW_MOST of those shown, in a
# document of at most NEW_LOOK_MOST objects.
NEW_MOST, NEW_LOOK_MOST = 20, 5000
# Tools whose answer names a spreadsheet: its view comes to the front.
SHEET_TOOLS = ("sheet_", "asm_bom", "bim_schedule", "param_")
# Tools that make a flat plan of a model (a 2D view at Z = 0, a cut sheet):
# looked at from the top.
PLAN_TOOLS = ("draft_2d_view", "bim_views", "bim_panel_out", "bim_grid")
# Families whose results are looked for under other things (a room under
# the roof, a surface inside a solid, a mesh copy on its source, another
# body in front of a Part Design feature). Not drawing pages, assemblies
# (their parts touch; a part in front is uncovered only by a part_ call) or
# CAM (the stock is made see-through by the CAM step itself). A sketch in
# edit is uncovered for every sketch_ call (_after). What holds the result
# (its body, level, assembly) is never made see-through (is_container).
UNCOVERED = ("bim_", "surface_", "meshobj_", "draft_", "part_", "fea_", "import_", "points_", "insp_", "material_",
             "pd_", "feature_", "object_", "link_", "compound_", "scad_")
# The keys that name the bodies a Part Design call worked in.
BODY_KEYS = ("body", "to", "from")


def out_names(name, args, body):
    """The names of what a call made or changed, the most exact first: the
    tool's own keys (OUT_MORE: its answer's, else its arguments'), then
    OUT_KEYS of the answer. Plain Python."""
    a = args if isinstance(args, dict) else {}
    b = body if isinstance(body, dict) else {}
    out = []

    def take(v):
        for x in v if isinstance(v, (list, tuple)) else [v]:
            if isinstance(x, dict):
                x = next((x[k] for k in ROW_KEYS if isinstance(x.get(k), str) and x[k]), None)
            if isinstance(x, str) and x and x not in out:
                out.append(x)

    for k in OUT_ONLY.get(name, ()):
        take(b.get(k) if b.get(k) else a.get(k))
    if out:
        return out
    for k in OUT_MORE.get(name, ()):
        take(b.get(k) if b.get(k) else a.get(k))
    for k in OUT_KEYS:
        take(b.get(k))
    return out


SUBS_MOST = 60


# Sketch tools that change geometry already there: what they changed is
# named in their arguments (ids stay).
SUB_ARGS = {"sketch_extend": ("geo",), "sketch_bspline": ("geo",), "sketch_to_bspline": ("geometry",)}


def sub_names(name, body, args=None):
    """The sketch's own names of what a sketch tool's answer says it added
    ("Edge3" for geometry id 2, "Constraint5" for constraint id 4,
    "ExternalEdge1" for outside geometry -3), to select in the open sketch;
    for a tool that changes geometry in place, the ids its arguments name
    (SUB_ARGS); a join's new B-spline. [] where none is given. Plain Python."""
    b = body if isinstance(body, dict) else {}
    a = args if isinstance(args, dict) else {}
    out = []

    def ints(v):
        return [x for x in v if isinstance(x, int) and not isinstance(x, bool)] if isinstance(v, (list, tuple)) else []

    if name == "sketch_constrain":
        out = [f"Constraint{i + 1}" for i in ints(b.get("added")) if i >= 0]
    elif name in ("sketch_external", "sketch_project"):
        # Both answer outside geometry ids (-3 down): sketch_project's
        # projected lines were never selected when read as Edge ids.
        out = [f"ExternalEdge{-i - 2}" for i in ints(b.get("ids")) if i <= -3]
    elif name.startswith("sketch_"):
        ids = []
        for row in b.get("added") if isinstance(b.get("added"), list) else []:
            ids += ints(row.get("ids")) if isinstance(row, dict) else ints([row])
        ids += ints(b.get("new"))
        ids += ints([b.get("bspline")])
        for k in SUB_ARGS.get(name, ()):
            v = a.get(k)
            ids += ints(v if isinstance(v, list) else [v])
        out = [f"Edge{i + 1}" for i in ids if i >= 0]
    return list(dict.fromkeys(out))[:SUBS_MOST]


def result_of(objs):
    """What to select and frame of the objects a call's answer names: the
    new or changed feature itself, not the body it is in (the whole body
    went green and nobody saw which feature was new); a body only when the
    answer names nothing else (a new body, a clone)."""
    inner = [o for o in objs if getattr(o, "TypeId", "") != "PartDesign::Body"]
    return inner or list(objs)

_log = []
_listeners = []
LOG_MAX = 200


def enabled():
    return FreeCAD.GuiUp and FreeCAD.ParamGet(PREFS).GetBool("Echo", True)


def delay_ms():
    return FreeCAD.ParamGet(PREFS).GetInt("EchoDelay", 350)


# A batch in the window: its first calls are shown at the full pace, so the
# person sees what kind of run it is; from the fourth changing call on the
# pause before each call is short and the paints that only let the window
# settle are skipped (the bench still comes up, the button lights, the
# result is selected); the batch's last call is shown at the full pace
# again, so the window ends on a state that can be read. Measured live, a
# changing call cost 0.35 to 2.5 s of echo, a 20-call batch 6 to 67 s.
BATCH_FULL = 3         # changing calls of a batch shown at the full pace
BATCH_DELAY_MS = 60    # the pause from then on (EchoBatchDelay)


def batch_delay_ms():
    """Mod/AgentLink EchoBatchDelay, ms: the pause before a batch's later
    calls. 0: no wait. -1: the same as EchoDelay (a batch is then paced as
    single calls are)."""
    return FreeCAD.ParamGet(PREFS).GetInt("EchoBatchDelay", BATCH_DELAY_MS)


def pace(batch, changing, full_ms, batch_ms, count=True):
    """How one call is shown: (mode, ms) — mode "full" (the pause full_ms
    and every settle paint) or "short" (the pause ms, no settle paints).
    batch: the session's batch_now ({ i, n, lastChange, … }; None for a
    call on its own); changing: whether this call changes the document
    (only those count towards BATCH_FULL; a read shown after them is short
    too); batch_ms: EchoBatchDelay. count: note this call in the batch
    (its "echoed": changing calls shown so far). Plain Python."""
    full_ms = max(0, int(full_ms or 0))
    if not isinstance(batch, dict):
        return "full", full_ms
    try:
        batch_ms = int(batch_ms)
    except (TypeError, ValueError):
        batch_ms = BATCH_DELAY_MS
    seen = int(batch.get("echoed") or 0)
    if changing and count:
        batch["echoed"] = seen + 1
    if batch_ms < 0:  # the same as EchoDelay
        return "full", full_ms
    i, n = batch.get("i"), batch.get("n")
    last = batch.get("lastChange")
    if isinstance(i, int) and ((isinstance(n, int) and i >= n - 1) or (isinstance(last, int) and i == last)):
        return "full", full_ms
    if seen < BATCH_FULL:
        return "full", full_ms
    # Never slower than a call on its own.
    return "short", min(batch_ms, full_ms)


def fit_animated(batch, mode):
    """Whether the view fit after a change may run FreeCAD's fit animation.
    A call on its own, and a batch's last shown call at the full pace: yes.
    Any other call of a batch: no — the view jumps to the same framing.

    FreeCAD's fit with animations on (the default) is ten nested event
    loops of 20 ms, each with a full redraw of the scene (FreeCAD 1.1
    source: src/Gui/View3DInventorViewer.cpp, viewAll and animatedViewAll
    (10, 20)): in a document of heavy shapes that was seconds a call,
    outside the call's own ms. Plain Python."""
    if mode != "full":
        return False
    if not isinstance(batch, dict):
        return True
    i, n, last = batch.get("i"), batch.get("n"), batch.get("lastChange")
    return isinstance(i, int) and ((isinstance(n, int) and i >= n - 1) or (isinstance(last, int) and i == last))


def log():
    return list(_log)


def listen(fn):
    _listeners.append(fn)


def _note(entry):
    _log.append(entry)
    del _log[:-LOG_MAX]
    for fn in list(_listeners):
        try:
            fn(entry)
        except Exception:
            pass


def _qt():
    from PySide import QtCore, QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return QtCore, QtGui, QtW


def _paint_flags(QtCore):
    f = getattr(QtCore.QEventLoop, "ExcludeUserInputEvents", None)
    if f is None:
        f = QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
    return f


def _paint(ms=0):
    """Let the window paint (and timers run) for ms, without taking the
    person's clicks and keys while a call is in hand (M7): no nested event
    loop that would let input change the document mid-call. The link's own
    timer will not start another call meanwhile (gui_link's in_call)."""
    import time as _t

    QtCore, _QtGui, _QtW = _qt()
    flags = _paint_flags(QtCore)
    end = _t.time() + max(0, ms) / 1000.0
    while True:
        try:
            QtCore.QCoreApplication.processEvents(flags, 30)
        except TypeError:
            QtCore.QCoreApplication.processEvents(flags)
        if _t.time() >= end:
            return
        _t.sleep(0.01)


def _wait(ms):
    """Let the window paint for ms without blocking it."""
    if ms <= 0:
        return
    _paint(ms)


PREFIX_NAME = {"pd": "Part Design", "part": "Part", "sketch": "Sketch", "bim": "BIM", "ifc": "IFC", "fea": "FEM",
               "td": "TechDraw", "draft": "Draft", "asm": "Assembly", "cam": "CAM", "meshobj": "Mesh", "sheet": "Spreadsheet",
               "insp": "Inspection", "points": "Points", "surface": "Surface", "note": "Note", "steps": "Steps", "view": "View",
               "doc": "Document", "object": "Object", "material": "Material",
               # Agent Link's own tools, by the part of FreeCAD they act on.
               "gui": "Window", "window": "Window", "report": "Report", "session": "Session", "dialog": "Dialog",
               "history": "History", "usage": "Usage", "tool": "Tools", "guide": "Guide", "batch": "Batch",
               "crash": "Crash", "queue": "Queue", "addon": "Add-ons", "app": "FreeCAD", "cmd": "Command",
               "menu": "Menu", "body": "Body", "export": "Export", "outputs": "Outputs", "measure": "Measure",
               "fem": "FEM", "scad": "OpenSCAD", "param": "Parameter", "robot": "Robot", "link": "Link"}


def declare(fam):
    """What an add-on's family says of its own tools, so no table here names
    them (read where families load: agentlink/families/__init__.py
    declared()). All optional, on the family module: SHOWN, names or name
    prefixes of read-only tools that still show something; OPENS, those of
    read-only tools that open a panel or dialog (they bring their bench up,
    as changing tools do; other reads never switch it); AREAS, {prefix:
    name} for the Activity list ('slice' gives 'Slice › …'); WORKBENCHES,
    {tool or prefix: workbench} to bring up for its tools (the longest
    match wins, so an add-on's "part_check" can go to another bench than core's
    "part_"); COMMANDS, {tool or prefix: command} whose button lights for
    its tools, or command_for(name, args) -> command or None; NO_BUTTON,
    names or prefixes of its tools that light no button at all; NO_ECHO,
    names or prefixes of its tools never shown as they run (no bench,
    button, caption or selection; still in Activity); WATCH, names or
    prefixes of its tools that only look at the window (a picture of it):
    they leave the last change's ring, words and selection as they are; PAGES,
    prefixes of its tools that work on a drawing page; PHRASES, {tool or
    prefix: template or templates} of what its calls did, in the Activity
    tab's words (agentlink/activity.py: "Sliced {object}")."""
    global SHOWN, OPENS
    shown = tuple(x for x in (getattr(fam, "SHOWN", ()) or ()) if isinstance(x, str) and x not in SHOWN)
    SHOWN = SHOWN + shown
    opens = tuple(x for x in (getattr(fam, "OPENS", ()) or ()) if isinstance(x, str) and x and x not in OPENS)
    OPENS = OPENS + opens
    for k, v in dict(getattr(fam, "AREAS", None) or {}).items():
        PREFIX_NAME.setdefault(k, v)
    for k, v in dict(getattr(fam, "WORKBENCHES", None) or {}).items():
        if not any(k == p for p, _ in WORKBENCH):
            WORKBENCH.append((k, v))
    for k, v in dict(getattr(fam, "COMMANDS", None) or {}).items():
        if isinstance(k, str) and isinstance(v, str):
            COMMANDS.setdefault(k, v)
    NO_BUTTON.update(k for k in (getattr(fam, "NO_BUTTON", None) or ()) if isinstance(k, str) and k)
    NO_ECHO.update(k for k in (getattr(fam, "NO_ECHO", None) or ()) if isinstance(k, str) and k)
    WATCH.update(k for k in (getattr(fam, "WATCH", None) or ()) if isinstance(k, str) and k)
    from . import activity

    activity.declare(fam)
    fn = getattr(fam, "command_for", None)
    if callable(fn) and fn not in COMMAND_FNS:
        COMMAND_FNS.append(fn)
    for k in getattr(fam, "PAGES", ()) or ():
        if isinstance(k, str) and k not in PAGES:
            PAGES.append(k)
    # Round 6: what an add-on's answers name (OUT_MORE: a maker's list of
    # bodies), what its reads worked on (SELECTS: {tool: answer key}), its
    # own words and selection (WORDS and SELECTS_FOR: callables).
    for k, v in dict(getattr(fam, "OUT_MORE", None) or {}).items():
        keys = (v,) if isinstance(v, str) else tuple(x for x in (v or ()) if isinstance(x, str))
        if isinstance(k, str) and keys:
            OUT_MORE[k] = tuple(dict.fromkeys(tuple(OUT_MORE.get(k, ())) + keys))
    for k, v in dict(getattr(fam, "SELECTS", None) or {}).items():
        keys = (v,) if isinstance(v, str) else tuple(x for x in (v or ()) if isinstance(x, str))
        if isinstance(k, str) and keys:
            SELECTS[k] = tuple(dict.fromkeys(tuple(SELECTS.get(k, ())) + keys))
    fn = getattr(fam, "WORDS", None)
    if callable(fn) and fn not in WORDS_FNS:
        WORDS_FNS.append(fn)
    fn = getattr(fam, "SELECTS_FOR", None)
    if callable(fn) and fn not in SELECT_FNS:
        SELECT_FNS.append(fn)


# Declared by add-ons (declare): {tool: answer keys} a read's answer names
# what it worked on under (selected after it, a Part Design body too);
# callables fn(name, args, body) -> words or None (the first words given
# replace the echo's own, the Activity row's too); callables fn(name, args,
# body, doc) -> [object names] or None (selected in place of what the echo
# would select).
SELECTS = {}
WORDS_FNS = []
SELECT_FNS = []


def declared_words(name, args, body):
    """An add-on's own words for this call (WORDS), or None. Never raises."""
    for fn in list(WORDS_FNS):
        try:
            w = fn(name, args if isinstance(args, dict) else {}, body if isinstance(body, dict) else {})
        except Exception:  # noqa: BLE001
            continue
        if isinstance(w, str) and w.strip():
            return w.strip()
    return None


def declared_selection(name, args, body, doc):
    """The names an add-on says to select after this call (SELECTS_FOR),
    or None. Never raises."""
    for fn in list(SELECT_FNS):
        try:
            got = fn(name, args if isinstance(args, dict) else {}, body if isinstance(body, dict) else {}, doc)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(got, str):
            got = [got]
        if isinstance(got, (list, tuple)) and any(isinstance(x, str) for x in got):
            return [x for x in got if isinstance(x, str)]
    return None


def selects_names(name, body):
    """The names a read's answer gives under its declared SELECTS keys.
    Plain Python."""
    b = body if isinstance(body, dict) else {}
    out = []
    for k in SELECTS.get(name, ()):
        v = b.get(k)
        for x in v if isinstance(v, (list, tuple)) else [v]:
            if isinstance(x, dict):
                x = next((x[r] for r in ROW_KEYS if isinstance(x.get(r), str) and x[r]), None)
            if isinstance(x, str) and x and x not in out:
                out.append(x)
    return out


def _area(name):
    """(area, what) for a tool's name: the longest declared key that fits
    (a whole name an add-on declares, or a prefix: 'note_', 'gui'), else
    its first word."""
    best = None
    for k in PREFIX_NAME:
        stem = k.rstrip("_")
        if name == stem or name.startswith(stem + "_"):
            if best is None or len(stem) > len(best):
                best = stem
    if best is None:
        head, _, rest = name.partition("_")
        return head.replace("-", " ").title(), rest
    key = best if best in PREFIX_NAME else best + "_"
    rest = name[len(best):].lstrip("_") if name != best else ""
    if not rest and "_" in name:  # a whole name declared: its verb is the last word
        rest = name.partition("_")[2]
    return PREFIX_NAME[key], rest


def did_name(name):
    """A tool's name as the Activity list shows it: 'Area › What', the
    what with a capital, the same way for every tool ('Window › Input',
    'Document › Save')."""
    area, rest = _area(name)
    what = rest.replace("_", " ").strip()
    return f"{area} › {what[:1].upper() + what[1:]}" if what else area


def _describe(name, args, body=None, template=None):
    """A tool call in words a person reads at a glance, the same as the
    Activity tab says it ("Padded Sketch by 20 mm", "Clicked Pin a Note"):
    agentlink/activity.py, never raw arguments or a folder. body: the
    call's answer, once there is one (the words then name what it made);
    template: the tool's own words (its "activity")."""
    from . import activity

    try:
        return activity.did(name, args, body, template)
    except Exception:
        return did_name(name)


def _view_widget():
    import FreeCADGui

    QtCore, _QtGui, QtW = _qt()
    mw = FreeCADGui.getMainWindow()
    area = mw.findChild(QtW.QMdiArea)
    # currentSubWindow too: activeSubWindow is None while FreeCAD is not the
    # application in front (the agent works in the background), and the
    # caption then went nowhere.
    sub = (area.activeSubWindow() or area.currentSubWindow()) if area else None
    return sub.widget() if sub else None


_caption = None
# Counts the captions shown: a caption's timer hides the label only while it
# still shows that caption (the words said again after a slow call are the
# same text, and the first timer hid them the moment they were back).
_caption_no = [0]
CAPTION_MARGIN, CAPTION_MAX, SLIDE_ROOM = 14, 420, 300


def caption_box(view_w, view_h, cap_w, cap_h):
    """(max width, x, y) of the caption in a 3D view this big: bottom right,
    clear of the left edge where the panel slides out (SLIDE_ROOM) and of
    the corners' view cube and axes above it; as wide as fits."""
    m = CAPTION_MARGIN
    most = max(160, min(CAPTION_MAX, view_w - SLIDE_ROOM - 2 * m))
    w = min(cap_w, most)
    x = max(m, view_w - w - m)
    y = max(m, view_h - cap_h - m)
    return most, x, y


def caption(text, ms=HOLD_MS):
    """A line of text over the 3D view, bottom right, gone after ms (or
    when newer words take its place)."""
    global _caption
    from .overlay import alive, later

    QtCore, _QtGui, QtW = _qt()
    host = _view_widget()
    if host is None or not alive(host):
        return
    if _caption is not None and not alive(_caption):
        _caption = None  # its view was closed, and the label with it: never touched again
    if _caption is None or _caption.parent() is not host:
        if _caption is not None:
            # Words held on another view (a page, the last document's 3D
            # view) go: only one caption is ever up.
            try:
                _caption.hide()
            except RuntimeError:
                pass
        _caption = QtW.QLabel(host)
        _caption.setStyleSheet("QLabel { background: rgba(20,22,26,200); color: #f2f2f2; border-radius: 6px; padding: 6px 10px; font-size: 13px; }")
        _caption.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
    _caption.setText("✦ Agent: " + text)
    _caption.setWordWrap(True)
    most, _x, _y = caption_box(host.width(), host.height(), host.width(), 0)
    _caption.setMaximumWidth(most)
    _caption.adjustSize()
    _most, x, y = caption_box(host.width(), host.height(), _caption.width(), _caption.height())
    _caption.move(x, y)
    _caption.show()
    _caption.raise_()
    lbl = _caption
    _caption_no[0] += 1
    # Our own timer (overlay.later: owned by a QObject of ours, stopped when
    # the label is destroyed, and run only while it is alive), never one
    # left on the label or its view.
    later(ms, lambda no=_caption_no[0]: _hide_later(lbl, text, no), lbl)


def _hide_later(lbl, text, no=None):
    """Hide the caption after its moment, unless it shows newer words (or
    the same words said again since: no, its count when shown) or is
    gone: closing a document deletes the 3D view and the label with it, and
    the timer then raised "Internal C++ object already deleted" in the
    Report view (as _later guards the lit buttons)."""
    from .overlay import alive

    if no is not None and no != _caption_no[0]:
        return
    if not alive(lbl):
        return
    try:
        if lbl.isVisible() and lbl.text().endswith(text):
            lbl.hide()
    except RuntimeError:
        pass


STATUS_HEAD = "Agent"


def say(words, ms=HOLD_MS, where=""):
    """The words over the 3D view and in the status bar (each on its own:
    no 3D view in front still gives the status bar its words). Returns the
    words."""
    import FreeCADGui

    words = str(words or "")
    try:
        caption(words, ms)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (caption): {e}\n")
    FreeCADGui.getMainWindow().statusBar().showMessage(STATUS_HEAD + where + ": " + words, ms + 1400)
    return words


def rings_off():
    """The buttons the echo lit for an earlier call, put out: called at the
    start of each changing call only (a ring is held until then, HOLD_MS),
    so a pattern never shows the primitive's ring, and a read or a picture
    of the window between two changes leaves the last change's ring lit.
    Never raises."""
    try:
        from . import overlay

        overlay.service().clear(owner="echo")
        return True
    except Exception:  # noqa: BLE001  (no window, or no overlay yet)
        return False


def flash_command(cmd, ms=HOLD_MS, settle=False, menu_ms=1300):
    """Light the toolbar button and the menu item that run cmd: the button
    for ms (held until the next changing call puts it out: rings_off),
    the menu item for menu_ms. settle:
    the bench was just switched, so one paint first, for its toolbars and
    menus to exist before their button can light. The button is lit on the
    overlay (agentlink/overlay.py), never by its stylesheet, so a theme's
    rules stay as they are."""
    from . import overlay, targets

    QtCore, QtGui, QtW = _qt()
    if settle:
        _paint()
    lit = []
    painter = overlay.service()
    flashed = False
    how, unseen = "none", []
    for act in _actions(cmd, QtW):
        for w in targets.associated(act):
            if isinstance(w, QtW.QToolButton):
                if painter.flash(w, ms):
                    flashed = True
                else:
                    unseen.append(w)
            elif isinstance(w, QtW.QMenu):
                # The menu item and its menu's title in bold for a moment
                # (no menu is opened: that would take the person's input).
                lit += [act, w.menuAction()]
    if flashed:
        how = "button"
    else:
        # Inside a toolbar dropdown (a group command): its button lights.
        try:
            for b, _m, _a in targets.group_buttons(cmd):
                if painter.flash(b, ms):
                    how = "group"
                else:
                    unseen.append(b)  # the dropdown's button, in the "»" list or on a hidden toolbar
        except Exception:  # noqa: BLE001  (a nicety; the call has run)
            pass
    if how == "none" and unseen and overflow_flash(unseen, _NO_LIGHT, ms, QtW):
        # The button is in its toolbar's "»" list (a narrow window). Round 4
        # lit the "»"; a ring there told the person nothing (td 047-052, fem
        # 034: which of the list's commands?). Round 6: no ring at all — a
        # shown button of the same command on another toolbar was lit above
        # when there is one, and the menu item is put in bold; the trace says
        # where the button is.
        how = "behind » (not lit)"
    if how == "none":
        # Said as it is (Echo.after's trace): a button that exists and is
        # not on screen, or a command with a menu item only. No other
        # button is lit in its place.
        how = "button not on screen" if unseen else "menu only" if lit else "no button"
    for a in dict.fromkeys(x for x in lit if x is not None):
        old = QtGui.QFont(a.font())
        f = QtGui.QFont(old)
        f.setBold(True)
        a.setFont(f)
        overlay.later(menu_ms, lambda a=a, old=old: _later(a, "setFont", old), a)
    return how


class _NoLight:
    """A painter that lights nothing: overflow_flash then only tells whether
    a button is in its toolbar's "»" list."""

    @staticmethod
    def flash(_w, _ms=0):
        return True


_NO_LIGHT = _NoLight()


def _actions(cmd, QtW):
    """The QActions that run cmd: FreeCAD's own list for the command
    (Gui.Command.get(cmd).getAction(), no walk over the window) when one of
    them has a toolbar button, else every action of the window named cmd
    (targets.actions: a walk over all of the window's actions, thousands,
    on every changing call)."""
    from . import targets

    try:
        import FreeCADGui

        c = FreeCADGui.Command.get(cmd)
        acts = [a for a in (c.getAction() if c is not None else None) or [] if a is not None]
        if any(isinstance(w, QtW.QToolButton) for a in acts for w in targets.associated(a)):
            return acts
    except Exception:  # noqa: BLE001  (an older FreeCAD, a stand-in)
        pass
    return targets.actions(cmd)


def in_overflow(rows, i):
    """Whether item i of a toolbar is in its "»" list: rows, the toolbar's
    items in order as (action shown, widget shown). Qt's toolbar layout
    hides the widgets that do not fit from the end; an item whose action is
    hidden, or a hidden widget with a shown one after it, is hidden for
    another reason (a command not available here, a widget the bench hides).
    Plain Python."""
    if not 0 <= i < len(rows):
        return False
    act, wid = rows[i]
    if not act or wid:
        return False
    return not any(w for a, w in rows[i + 1:] if a)


def _toolbar_of(w, QtW):
    bar = w.parentWidget()
    while bar is not None and not isinstance(bar, QtW.QToolBar):
        bar = bar.parentWidget()
    return bar


def overflow_flash(buttons, painter, ms, QtW):
    """The "»" button of the toolbar that holds one of buttons lit (Qt's
    qt_toolbar_ext_button: the list of what does not fit), only when that
    toolbar is shown, its "»" is shown, and the button is one Qt moved into
    the list (in_overflow). True when one was lit. Never raises."""
    for w in buttons:
        try:
            bar = _toolbar_of(w, QtW)
            if bar is None or not bar.isVisible():
                continue  # a toolbar the person hid: no "»" stands for it
            ext = bar.findChild(QtW.QToolButton, "qt_toolbar_ext_button")
            if ext is None or not ext.isVisible():
                continue
            acts = [a for a in bar.actions() if not a.isSeparator()]
            rows, at = [], None
            for k, a in enumerate(acts):
                wid = bar.widgetForAction(a)
                rows.append((bool(a.isVisible()), bool(wid is not None and wid.isVisible())))
                if wid is w:
                    at = k
            if at is None or not in_overflow(rows, at):
                continue
            if painter.flash(ext, ms):
                return True
        except Exception:  # noqa: BLE001  (a deleted toolbar)
            continue
    return False


def _later(obj, method, value):
    """Put a button or menu item back after its moment lit, unless it is gone:
    a workbench switch in the meantime deletes its toolbars' actions, and
    calling into one raised "Internal C++ object already deleted" in the
    Report view (GUI pass on the Mac)."""
    from .overlay import alive

    if not alive(obj):
        return
    try:
        getattr(obj, method)(value)
    except RuntimeError:
        pass


def fit(animate=True, selection=False):
    """Frame the part in the 3D view in front — only a live 3D view of an
    open document, and not while a restart is reopening documents (a view
    being made or torn down then crashes FreeCAD in its fit animation).
    animate: False frames it at once: the view's animation is switched off
    for the fit and put back as it was (fit_animated says when).
    selection: frame what is selected (what the call made), with a margin,
    not the whole document: in a document of many parts the new one was a
    few pixels. The whole document when nothing selected can be framed."""
    try:
        import FreeCADGui

        from . import restart_mark

        if restart_mark.read() is not None:
            return False
        gd = FreeCADGui.ActiveDocument
        if gd is None or FreeCAD.ActiveDocument is None or gd.Document.Name not in FreeCAD.listDocuments():
            return False
        v = gd.ActiveView
        if v is None or not hasattr(v, "getSceneGraph") or not hasattr(v, "fitAll"):
            return False
        was = None
        if not animate:
            try:
                was = bool(v.isAnimationEnabled())
                if was:
                    v.setAnimationEnabled(False)
            except Exception:
                was = None
        how = "all"
        try:
            if selection and _fit_selection(v):
                how = "selection"
            else:
                v.fitAll()
        finally:
            if was:
                try:
                    v.setAnimationEnabled(True)
                except Exception:
                    pass
        return how
    except Exception as e:
        _plog(f"Agent Link fit: {e}\n")
        return False


def fit_on(objs, animate=True):
    """The view framed on objs (selected for it), not on the whole
    document. "selection" when it was, else False (the caller frames the
    whole document)."""
    objs = list(objs or ())
    if not objs:
        return False
    _select(objs)
    return "selection" if fit(animate=animate, selection=True) == "selection" else False


def _fit_selection(v):
    """The view framed on the selection (FreeCAD's own View > Standard
    views > Fit selection: the box of what is selected, as its view
    providers draw it), then one zoom step out for a margin. False when it
    was not done (nothing selected, or a view that does not take it): the
    caller then fits the whole document."""
    import FreeCADGui

    try:
        if not FreeCADGui.Selection.getSelection():
            return False
        # FreeCAD frames the box its view providers give (View3DInventorViewer
        # ::viewSelection) and does nothing when that box is not valid (a
        # sketch in edit: its shape node is empty), with no word of it — the
        # view stayed 5 mm wide on the origin after a new sketch's first
        # lines. A camera that did not move is a frame not made.
        cam0 = _camera(v)
        send = getattr(v, "sendMessage", None)
        if callable(send):
            if send("ViewSelection") is False:
                return False
        else:
            FreeCADGui.SendMsgToActiveView("ViewSelection")
        if cam0 is not None and _camera(v) == cam0:
            return False
    except Exception:  # noqa: BLE001
        return False
    try:
        if callable(getattr(v, "zoomOut", None)):
            v.zoomOut()
    except Exception:  # noqa: BLE001  (a margin only)
        pass
    return True


def framed(objs):
    """Of what a call made, the objects the view can be framed on: those
    shown that have a shape with a size. A new empty body or sketch, or a
    hidden object, has no box: the whole document is framed then."""
    out = []
    for o in objs or ():
        try:
            vo = getattr(o, "ViewObject", None)
            if vo is not None and not vo.Visibility:
                continue
            if getattr(o, "Shape", None) is None and _box(o) is not None:
                # A mesh or a point cloud: no Shape, a box all the same (the
                # whole document was framed for meshobj_from_shape,
                # points_mesh, points_merge, points_structure: round 6).
                out.append(o)
                continue
            sh = getattr(o, "Shape", None)
            if sh is None:
                # A link (a part put into an assembly) has no Shape of its
                # own: Part's reading of it, placed.
                import Part

                sh = Part.getShape(o)
            if sh is None or sh.isNull():
                continue
            bb = sh.BoundBox
            if bb.isValid() and bb.DiagonalLength > 0:
                out.append(o)
        except Exception:  # noqa: BLE001
            continue
    return out


def _camera(v):
    """The view's camera as text (Coin's own dump), to tell whether a frame
    moved it; None when the view cannot say."""
    try:
        fn = getattr(v, "getCamera", None)
        return fn() if callable(fn) else None
    except Exception:  # noqa: BLE001
        return None


# ---- a sketch framed whole (round 3, item 3) ------------------------------------------------

SKETCH_EMPTY_MM = 100.0  # a new, empty sketch: this much of its plane around its origin
ROBOT_MM = 1500.0        # a robot framed: at least this much around its base and tool point


def box_of(points):
    """(xmin, ymin, zmin, xmax, ymax, zmax) of (x, y, z) points, or None.
    Plain Python."""
    pts = [p for p in points or () if isinstance(p, (tuple, list)) and len(p) == 3]
    if not pts:
        return None
    return (min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts))


def grown(box, margin=0.08, least=2.0):
    """box grown by margin of its largest side on each side, and to least mm
    at the smallest (a point or a single line still gets a view around it).
    Plain Python."""
    if box is None:
        return None
    x0, y0, z0, x1, y1, z1 = box
    big = max(x1 - x0, y1 - y0, z1 - z0, least)
    pad = big * margin
    out = []
    for lo, hi in ((x0, x1), (y0, y1), (z0, z1)):
        if hi - lo < least:
            mid = (lo + hi) / 2.0
            lo, hi = mid - least / 2.0, mid + least / 2.0
        out.append((lo - pad, hi + pad))
    return (out[0][0], out[1][0], out[2][0], out[0][1], out[1][1], out[2][1])


def _corners(bb):
    return [(x, y, z) for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax) for z in (bb.ZMin, bb.ZMax)]


def sketch_box(sk):
    """The box of a sketch's own geometry in the document's coordinates (its
    lines as they are now, whether or not the sketch was recomputed, and
    whether or not it is open: a sketch in edit draws its lines apart from
    its shape, so FreeCAD's Fit selection found no box). An empty sketch:
    SKETCH_EMPTY_MM of its plane around its origin. None when it cannot be
    read."""
    try:
        pl = sk.getGlobalPlacement()
    except Exception:  # noqa: BLE001
        try:
            pl = sk.Placement
        except Exception:  # noqa: BLE001
            return None
    local = []
    try:
        geos = list(getattr(sk, "Geometry", None) or [])
    except Exception:  # noqa: BLE001
        geos = []
    for g in geos:
        try:
            bb = g.toShape().BoundBox
            if bb.isValid():
                local += _corners(bb)
        except Exception:  # noqa: BLE001  (a geometry with no shape: skipped)
            continue
    if not local:
        h = SKETCH_EMPTY_MM / 2.0
        local = [(x, y, 0.0) for x in (-h, h) for y in (-h, h)]
    try:
        pts = []
        for x, y, z in local:
            p = pl.multVec(FreeCAD.Vector(x, y, z))
            pts.append((p.x, p.y, p.z))
        return box_of(pts)
    except Exception:  # noqa: BLE001
        return None


def frame_box(v, box):
    """The view framed on box (grown()), its direction kept: Coin's own
    viewBoundingBox on the view's camera, as FreeCAD's Fit selection does.
    True when done. Never raises."""
    box = grown(box)
    if v is None or box is None:
        return False
    try:
        from pivy import coin

        cam = v.getCameraNode()
        w, h = v.getSize() if callable(getattr(v, "getSize", None)) else (1, 1)
        aspect = float(w) / float(h) if h else 1.0
        cam.viewBoundingBox(coin.SbBox3f(*box), aspect, 1.0)
        return True
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (frame box): {e}\n")
        return False


# ---- scene-only marks and colours (round 6) --------------------------------------------------

SCENE_OWNER = "echo-scene"


def scene_marks(points, lines=(), colour="#e8a33d"):
    """Marks drawn in the 3D view's scene only (agentlink/annotate.py), put
    away at the next changing call (scene_clear). The count. Never raises."""
    try:
        from . import annotate

        return annotate.service().marks(SCENE_OWNER, points, lines, colour)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (scene marks): {e}\n")
        return 0


def scene_field(V, F, colours, per_face=False):
    try:
        from . import annotate

        return annotate.service().field(SCENE_OWNER, V, F, colours, per_face)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (scene colours): {e}\n")
        return 0


def scene_clear():
    """The echo's scene-only marks and colours put away; the objects hidden
    under them shown again (_hid_for_scene). True when there was any.
    Never raises."""
    had = False
    try:
        from . import annotate

        svc = annotate.service()
        had = SCENE_OWNER in getattr(svc, "roots", {})
        svc.clear(SCENE_OWNER)
    except Exception:  # noqa: BLE001
        pass
    while _view_props:
        doc_name, name, prop, old = _view_props.pop()
        try:
            if doc_name in FreeCAD.listDocuments():
                o = FreeCAD.getDocument(doc_name).getObject(name)
                if o is not None and getattr(o, "ViewObject", None) is not None:
                    setattr(o.ViewObject, prop, old)
                    had = True
        except Exception:  # noqa: BLE001
            continue
    while _hid_for_scene:
        doc_name, name = _hid_for_scene.pop()
        try:
            if doc_name in FreeCAD.listDocuments():
                o = FreeCAD.getDocument(doc_name).getObject(name)
                if o is not None and getattr(o, "ViewObject", None) is not None:
                    o.ViewObject.Visibility = True
                    had = True
        except Exception:  # noqa: BLE001
            continue
    return had


# Objects hidden while a colour map of the scene is drawn on them (document,
# name): shown again at the next changing call.
_hid_for_scene = []


def hide_for_scene(objs):
    """objs hidden (view state) while the scene's colours stand for them;
    their labels. Never raises."""
    done = []
    for o in objs or ():
        try:
            if _seen(o):
                o.ViewObject.Visibility = False
                _hid_for_scene.append((o.Document.Name, o.Name))
                done.append(o.Label)
        except Exception:  # noqa: BLE001
            continue
    return done


def robot_paths(doc):
    """Each robot trajectory's waypoints [(x, y, z)], placed by its Base.
    Never raises."""
    out = []
    try:
        for t in getattr(doc, "Objects", ()) or ():
            if getattr(t, "TypeId", "") != "Robot::TrajectoryObject":
                continue
            try:
                base = getattr(t, "Base", None)
                line = []
                for w in t.Trajectory.Waypoints:
                    p = base.multiply(w.Pos).Base if base is not None else w.Pos.Base
                    line.append((p.x, p.y, p.z))
                if line:
                    out.append(line)
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


# ---- framing without labels (round 6, item 5) ----------------------------------------------

# Draft and BIM objects that are words or marks, not the model: framing on
# them framed a label (Draft's Proxy.Type).
ANNOTATION_KINDS = ("Label", "Text", "LinearDimension", "AngularDimension", "Dimension", "DraftText", "AnnotationLabel")
ANNOTATION_TYPES = ("App::Annotation", "App::AnnotationLabel", "App::MeasureDistance", "Measure::MeasureDistance",
                    "Measure::MeasureBase", "Measure::MeasureDistanceDetached")


def is_annotation(o):
    """Words or a mark, not part of the model (a Draft label, text or
    dimension, an annotation, a measurement). Never raises."""
    try:
        if getattr(o, "TypeId", "") in ANNOTATION_TYPES:
            return True
        proxy = getattr(o, "Proxy", None)
        return str(getattr(proxy, "Type", "") or "") in ANNOTATION_KINDS
    except Exception:  # noqa: BLE001
        return False


def is_bim_container(o):
    """A BIM level, building, site (an Arch BuildingPart and its kin): its
    view draws a label and a level line that Fit selection frames."""
    try:
        proxy = getattr(o, "Proxy", None)
        return type(proxy).__name__ in ("BuildingPart", "Floor", "Building", "Site", "Project") or \
            str(getattr(proxy, "Type", "") or "") in ("BuildingPart", "Floor", "Building", "Site")
    except Exception:  # noqa: BLE001
        return False


def _union(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
            max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes))


FRAME_LOOK_MOST = 2000


def members_box(objs):
    """The box of what objs are, their annotations left out: a container's
    shown members (all levels down), a plain object its own. None when
    there is nothing with a size. Never raises."""
    boxes, seen = [], set()
    try:
        todo = list(objs or ())
        while todo and len(seen) < FRAME_LOOK_MOST:
            o = todo.pop()
            if id(o) in seen:
                continue
            seen.add(id(o))
            if is_annotation(o):
                continue
            if is_container(o) or is_bim_container(o):
                todo += list(getattr(o, "Group", None) or ())
                continue
            if _hidden(o):
                continue
            b = _box(o)
            if b is not None:
                boxes.append(_tuple(b))
    except Exception:  # noqa: BLE001
        pass
    return _union(boxes)


def model_box(doc):
    """The box of every shown object of doc that is not an annotation nor a
    container (the building, not its labels). Never raises."""
    try:
        objs = [o for o in list(getattr(doc, "Objects", ()) or ())[:FRAME_LOOK_MOST]
                if not is_annotation(o) and not is_container(o) and not is_bim_container(o) and _seen(o)]
        return _union(_tuple(b) for b in (_box(o) for o in objs) if b is not None)
    except Exception:  # noqa: BLE001
        return None


# ---- a result hidden under other things (round 3, item 4) ---------------------------------

# Objects the echo made see-through for a result under them: (document
# name, object name, the Transparency it had), put back at the next changing
# call (restore_covers). Names, never the objects: a document closed or an
# object deleted in between is looked up and found gone, not touched.
_covers = []
COVER_ALPHA = 80      # how see-through a cover is made (FreeCAD's Transparency, 0-100)
COVERS_MOST = 30      # at most this many made see-through for one call
COVER_LOOK_MOST = 400  # documents with more shown objects than this are not searched


def _box(o):
    """An object's box (Shape, else Mesh, else a point cloud's Points), or
    None."""
    try:
        for attr in ("Shape", "Mesh", "Points"):
            sh = getattr(o, attr, None)
            if sh is None:
                continue
            bb = sh.BoundBox
            if bb.isValid() and bb.DiagonalLength > 0:
                return bb
    except Exception:  # noqa: BLE001
        return None
    return None


def covers(made_boxes, others):
    """Of others ([(key, box)]: the shown objects that are not the result),
    the keys of those that hide a result: their box holds the middle of a
    result's box and is at least nine tenths of its size (a roof over a room,
    a solid round a surface inside it, a source mesh under its copy). Boxes
    are (xmin, ymin, zmin, xmax, ymax, zmax). Plain Python."""
    out = []
    for key, b in others:
        for m in made_boxes:
            mid = [(m[i] + m[i + 3]) / 2.0 for i in range(3)]
            inside = all(b[i] - 1e-6 <= mid[i] <= b[i + 3] + 1e-6 for i in range(3))
            size_m = max(m[i + 3] - m[i] for i in range(3))
            size_b = max(b[i + 3] - b[i] for i in range(3))
            if inside and size_b >= 0.9 * size_m:
                out.append(key)
                break
    return out


def _tuple(bb):
    return (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)


def sight_hits(box, point, direction, eps=1e-6):
    """Whether the line of sight from point back to the camera (the camera
    looks along direction; orthographic, as FreeCAD's default view) passes
    through box (xmin, ymin, zmin, xmax, ymax, zmax) in front of the point.
    A box that holds the point does not count here (covers() judges those,
    by size). Plain Python."""
    ln = sum(c * c for c in direction) ** 0.5
    if ln <= 0:
        return False
    r = [-c / ln for c in direction]
    t0, t1 = -float("inf"), float("inf")
    for i in range(3):
        lo, hi, o = box[i], box[i + 3], point[i]
        if abs(r[i]) < 1e-12:
            if o < lo - eps or o > hi + eps:
                return False
            continue
        a, b = (lo - o) / r[i], (hi - o) / r[i]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    return t1 >= t0 and t0 > eps


def covers_in_view(made_boxes, others, direction):
    """Of others ([(key, box)]), the keys of those between a result and the
    camera, seen along direction: the line of sight from the middle of a
    result's box passes through them (the roof over a room seen from above,
    the house in front of a truss behind it, the plate in front of a sketch
    face on). Plain Python."""
    if not direction:
        return []
    out = []
    for key, b in others:
        if any(sight_hits(b, p, direction) for m in made_boxes for p in sight_points(m)):
            out.append(key)
    return out


SIGHT_INSET = 0.15


def sight_points(m):
    """Where lines of sight start from a result's box: a 3 x 3 x 3 lattice
    over it (its middle, the middles of its faces and edges, its corners),
    pulled SIGHT_INSET of the way to the middle; a flat box gives 9. Round
    4 took the middle alone, and a body beside a sketch or seen edge-on, in
    front of part of it only, was missed (sk 024, 037-040, 060). Plain
    Python."""
    mid = [(m[i] + m[i + 3]) / 2.0 for i in range(3)]
    out = [tuple(mid)]
    for x in (m[0], mid[0], m[3]):
        for y in (m[1], mid[1], m[4]):
            for z in (m[2], mid[2], m[5]):
                p = tuple(c + (mc - c) * SIGHT_INSET for c, mc in zip((x, y, z), mid))
                if p not in out:
                    out.append(p)
    return out


# Objects that hold others (a body, a part, a folder, a BIM level or building,
# an assembly): never made see-through for what is inside them (their box
# holds it by nature, and the whole assembly went see-through: asm 049).
CONTAINER_TYPES = ("PartDesign::Body", "App::Part", "App::DocumentObjectGroup", "Assembly::AssemblyObject",
                   "App::DocumentObjectGroupPython", "App::LinkGroup")


def is_container(o):
    try:
        if getattr(o, "TypeId", "") in CONTAINER_TYPES:
            return True
        if "Group" in (getattr(o, "PropertiesList", None) or ()) and getattr(o, "Shape", None) is None:
            return True
        proxy = getattr(o, "Proxy", None)
        return type(proxy).__name__ in ("BuildingPart", "Floor", "Building", "Site", "Project")
    except Exception:  # noqa: BLE001
        return False


# Boxes of the objects looked at by uncover(), by (document, name): kept
# while the object's shape is the same one (its hash; a mesh's counts), so a
# BIM model's hundred walls are not measured again on every call.
_boxes = {}
BOXES_MOST = 4000


def _stamp(o):
    try:
        sh = getattr(o, "Shape", None)
        if sh is not None:
            return ("s", sh.hashCode())
        m = getattr(o, "Mesh", None)
        if m is not None:
            return ("m", m.CountPoints, m.CountFacets)
        p = getattr(o, "Points", None)
        if p is not None:
            return ("p", p.CountPoints)
    except Exception:  # noqa: BLE001
        pass
    return None


def _box_of(o):
    """o's box as a tuple, or None; from _boxes when its shape is the same."""
    try:
        key = (o.Document.Name, o.Name)
    except Exception:  # noqa: BLE001
        key = None
    st = _stamp(o) if key is not None else None
    if st is not None and key in _boxes and _boxes[key][0] == st:
        return _boxes[key][1]
    b = _box(o)
    t = _tuple(b) if b is not None else None
    if st is not None:
        if len(_boxes) > BOXES_MOST:
            _boxes.clear()
        _boxes[key] = (st, t)
    return t


def view_direction():
    """The active 3D view's direction (x, y, z), or None."""
    try:
        import FreeCADGui

        d = FreeCADGui.ActiveDocument.ActiveView.getViewDirection()
        return (d.x, d.y, d.z)
    except Exception:  # noqa: BLE001
        return None


def uncover(doc, made, boxes=None, direction=None):
    """What hides a result made see-through, as view state only (each cover's
    ViewObject.Transparency; FreeCAD does not mark a document modified for
    it), put back at the next changing call: a shown object whose box holds
    the result (covers()) or that stands between it and the camera
    (covers_in_view(), along direction, else the active view's). The result
    itself and what holds it (its body, part, folder, level, assembly:
    is_container) are never touched; what it is built from may be (a host
    slab round its bars, the plate over a sketch). boxes: the result's boxes
    when its shape does not tell (a sketch in edit: sketch_box). Returns the
    labels made see-through. Never raises."""
    done = []
    try:
        mine = [b for b in boxes or () if b is not None]
        if not mine:
            got = [(o, _box(o)) for o in made or ()]
            mine = [_tuple(b) for _o, b in got if b is not None]
        if not mine:
            return done
        near = set()
        for o in made:
            near.add(id(o))
            try:
                near.update(id(x) for x in getattr(o, "InListRecursive", None) or () if is_container(x))
            except Exception:  # noqa: BLE001
                continue
        shown = []
        for o in list(getattr(doc, "Objects", ()) or ()):
            if id(o) in near or not _seen(o):
                continue
            shown.append(o)
            if len(shown) > COVER_LOOK_MOST:
                return done
        others = []
        for o in shown:
            vo = getattr(o, "ViewObject", None)
            try:
                if "Transparency" not in getattr(vo, "PropertiesList", ()) or int(vo.Transparency or 0) >= COVER_ALPHA:
                    continue
            except Exception:  # noqa: BLE001
                continue
            if is_container(o):
                continue
            b = _box_of(o)
            if b is not None:
                others.append((o, b))
        if direction is None:
            direction = view_direction()
        hit = covers(mine, others)
        seen = {id(o) for o in hit}
        hit += [o for o in covers_in_view(mine, [(o, b) for o, b in others if id(o) not in seen], direction)]
        for o in hit[:COVERS_MOST]:
            vo = o.ViewObject
            _covers.append((o.Document.Name, o.Name, int(vo.Transparency or 0)))
            vo.Transparency = COVER_ALPHA
            done.append(getattr(o, "Label", "?"))
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (uncover): {e}\n")
    return done


def restore_covers():
    """What uncover() made see-through, put back as it was. The labels put
    back. Never raises."""
    back = []
    while _covers:
        doc_name, name, was = _covers.pop()
        try:
            if doc_name not in FreeCAD.listDocuments():
                continue  # closed since: nothing to put back
            o = FreeCAD.getDocument(doc_name).getObject(name)
            vo = getattr(o, "ViewObject", None) if o is not None else None
            if vo is None:
                continue  # deleted since
            vo.Transparency = was
            back.append(o.Label)
        except Exception:  # noqa: BLE001
            continue
    return back


SEGMENT_COLOURS = [(0.90, 0.62, 0.0), (0.34, 0.71, 0.91), (0.0, 0.62, 0.45), (0.94, 0.89, 0.26),
                   (0.0, 0.45, 0.70), (0.84, 0.37, 0.0), (0.80, 0.47, 0.65), (0.6, 0.6, 0.6)]


def map_shown(session, name, args):
    """A read's colour map drawn on the model in the 3D view's scene only
    (round 6, mesh 012: the curvature map was never seen): the map of the
    same name view_render draws (render.MAPS), coloured as it colours it.
    {map, range, triangles}, or None. Never raises."""
    try:
        from . import render

        fn = (render.MAPS.get(name) or (None,))[0]
        if fn is None:
            return None
        m = fn(session, dict(args or {}))
        import numpy as np

        try:
            from . import annotate

            annotate.service().clear(SCENE_OWNER)  # one map at a time
        except Exception:  # noqa: BLE001
            pass
        drawn = 0
        lo = hi = None
        for layer in m.get("layers") or ():
            vals = np.asarray(layer["values"], dtype=float)
            fin = vals[np.isfinite(vals)]
            if not len(fin):
                continue
            rng = m.get("range")
            if rng:
                lo, hi = float(rng[0]), float(rng[1])
            else:
                lo, hi = float(np.percentile(fin, 1)), float(np.percentile(fin, 99))
            if hi <= lo:
                hi = lo + 1e-6
            drawn += scene_field(layer["V"], layer["F"], render.colours_for(vals, lo, hi, m.get("cmap", "jet")))
        if not drawn:
            return None
        return {"map": name, "range": [round(lo, 6), round(hi, 6)], "triangles": drawn}
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (map {name}): {e}\n")
        return None


SEGMENTS_FACETS_MOST = 300000
# Reads whose answer is a map view_render can draw: the map's name.
READ_MAPS = {"meshobj_curvature": "curvature"}


def segments_drawn(doc, args, body):
    """meshobj_segments' regions coloured in the scene (round 6, mesh 009:
    the tool finds them with Mesh.getPlanarSegments and keeps none on the
    mesh, so FreeCAD's own highlightSegments had nothing to colour): the
    same search again, each region its own colour. The regions drawn, or
    None. Never raises."""
    try:
        a = args if isinstance(args, dict) else {}
        if str(a.get("kind", "planar")) != "planar":
            return None
        objs = _objects(doc, [(body or {}).get("mesh"), a.get("mesh")])
        o = next((x for x in objs if getattr(x, "Mesh", None) is not None), None)
        if o is None or o.Mesh.CountFacets > SEGMENTS_FACETS_MOST:
            return None
        m = o.Mesh
        segs = m.getPlanarSegments(float(a.get("deviation", 0.01)), int(a.get("minFacets", 20)))
        if not segs:
            return None
        pl = o.Placement if hasattr(o, "Placement") else None
        V = []
        for p in m.Points:
            q = pl.multVec(p.Vector) if pl is not None else p.Vector
            V.append((q.x, q.y, q.z))
        F, cols = [], []
        facets = m.Facets
        segs = sorted(segs, key=len, reverse=True)
        for i, seg in enumerate(segs):
            c = SEGMENT_COLOURS[i % len(SEGMENT_COLOURS)]
            for k in seg:
                F.append(tuple(facets[int(k)].PointIndices))
                cols.append(c)
        if not scene_field(V, F, cols, per_face=True):
            return None
        return len(segs)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (mesh segments): {e}\n")
        return None


def segments_shown(made):
    """A mesh's segments each in its own colour, as Mesh's own segment
    tools show them (ViewProviderMesh.highlightSegments: the scene only, no
    property). The labels coloured. Never raises."""
    done = []
    for o in made or ():
        try:
            n = int(o.Mesh.countSegments())
            if n <= 0:
                continue
            o.ViewObject.highlightSegments([SEGMENT_COLOURS[i % len(SEGMENT_COLOURS)] for i in range(n)])
            done.append(o.Label)
        except Exception:  # noqa: BLE001
            continue
    return done


# ---- a body's tip shown (P4) ----------------------------------------------------------------

def _shaped(o):
    sh = getattr(o, "Shape", None)
    try:
        return sh is not None and not sh.isNull()
    except Exception:  # noqa: BLE001
        return False


def _seen(o):
    vo = getattr(o, "ViewObject", None)
    try:
        return vo is not None and bool(vo.Visibility)
    except Exception:  # noqa: BLE001
        return False


def _is_feature(o):
    try:
        return bool(o.isDerivedFrom("PartDesign::Feature"))
    except Exception:  # noqa: BLE001
        return False


def tip_shown(body):
    """A Part Design body left showing its tip, as FreeCAD's own commands
    leave it: the tip visible, the body's other solid features hidden.
    A body shows through one feature. A feature made by the Python API is
    visible from the start and FreeCAD then hides the body's others: a
    MultiTransform's steps are made after it, have no shape of their own
    and so left the body showing nothing; a feature moved out left the
    old body with its tip still hidden. Only a body that is itself shown
    and whose tip has a shape; sketches, datums and binders are not
    touched. True when something was changed. Never raises."""
    try:
        if getattr(body, "TypeId", "") != "PartDesign::Body" or not _seen(body):
            return False
        tip = getattr(body, "Tip", None)
        if tip is None or not _shaped(tip) or getattr(tip, "ViewObject", None) is None:
            return False
        others = [o for o in body.Group if o is not tip and _is_feature(o) and _seen(o)]
        if _seen(tip) and not others:
            return False
        for o in others:
            o.ViewObject.Visibility = False
        if not _seen(tip):
            tip.ViewObject.Visibility = True
        return True
    except Exception as e:  # noqa: BLE001
        if FreeCAD is not None:
            FreeCAD.Console.PrintLog(f"Agent Link echo (tip shown): {e}\n")
        return False


def bodies_of(doc, args, body, made):
    """The Part Design bodies a call worked in: those its arguments and
    answer name (BODY_KEYS) and those that hold what it made."""
    names = [src.get(k) for src in (args, body) if isinstance(src, dict) for k in BODY_KEYS]
    out = []
    for o in list(made or ()) + _objects(doc, names):
        cands = [o] + [p for p in getattr(o, "InList", ()) or ()]
        for b in cands:
            if getattr(b, "TypeId", "") == "PartDesign::Body" and b not in out:
                out.append(b)
    return out


# ---- datums put away once used (P8) --------------------------------------------------------

# Datum objects a call made, by document name: hidden by the echo once a
# later call has made a solid (the datum has then done its job), each once
# only — a datum the person shows again stays shown, and a datum the person
# made is never touched.
_fresh_datums = {}
DATUM_TYPES = ("PartDesign::Plane", "PartDesign::Line", "PartDesign::Point", "PartDesign::CoordinateSystem",
               "Part::DatumPlane", "Part::DatumLine", "Part::DatumPoint", "Part::LocalCoordinateSystem")


def is_datum(o):
    try:
        if getattr(o, "TypeId", "") in DATUM_TYPES:
            return True
        return bool(o.isDerivedFrom("Part::Datum"))
    except Exception:  # noqa: BLE001
        return False


def _has_solid(o):
    try:
        sh = getattr(o, "Shape", None)
        return sh is not None and not sh.isNull() and bool(sh.Solids)
    except Exception:  # noqa: BLE001
        return False


def datums_after(doc, made):
    """Note the datums this call made; when it made a solid instead, hide
    those noted earlier in doc (view state only: a view provider's
    Visibility, which FreeCAD keeps from marking the object touched or the
    document modified, as the space bar does). Returns the names hidden.
    Never raises."""
    hidden = []
    try:
        key = doc.Name
        made = list(made or ())
        new = [o.Name for o in made if is_datum(o)]
        if new:
            _fresh_datums.setdefault(key, [])
            _fresh_datums[key] += [n for n in new if n not in _fresh_datums[key]]
            return hidden
        if not any(_has_solid(o) and not is_datum(o) for o in made):
            return hidden
        for n in _fresh_datums.pop(key, []):
            o = doc.getObject(n)
            vo = getattr(o, "ViewObject", None) if o is not None else None
            try:
                if vo is not None and vo.Visibility:
                    vo.Visibility = False
                    hidden.append(n)
            except Exception:  # noqa: BLE001
                continue
    except Exception as e:  # noqa: BLE001
        if FreeCAD is not None:
            FreeCAD.Console.PrintLog(f"Agent Link echo (datums): {e}\n")
    return hidden


# ---- exploded-view lines cleared after a collapse (A9) ------------------------------------

def explode_lines_off(doc):
    """The dashed lines of the doc's exploded-view steps taken off the view
    once the parts are back together: Assembly's step view providers draw
    them (CommandCreateView.py, ViewProviderExplodedViewStep.redrawLines)
    and nothing clears them when the parts move back. Only the lines in the
    3D scene: no property changes. The count of steps cleared. Never raises."""
    n = 0
    try:
        for o in list(getattr(doc, "Objects", ()) or ()):
            try:
                proxy = getattr(getattr(o, "ViewObject", None), "Proxy", None)
                fn = getattr(proxy, "redrawLines", None)
                if callable(fn):
                    fn(o, [])
                    n += 1
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return n


def _objects(doc, names):
    out = []
    for n in names:
        if not isinstance(n, str):
            continue
        o = doc.getObject(n) or next((x for x in doc.Objects if x.Label == n), None)
        if o is not None and o not in out:
            out.append(o)
    return out


# Counts the selections made here: a result's "lit for a moment" timer
# clears the selection only while it is still that result's (at a batch's
# short pace the next call's selection is there before the timer fires).
_selected = [0]


def _clear_if(mark):
    """Clear the selection unless a newer one was made here since mark."""
    if _selected[0] != mark:
        return False
    try:
        import FreeCADGui

        FreeCADGui.Selection.clearSelection()
    except Exception:  # noqa: BLE001 - the window is closing
        return False
    return True


def sel_path(o):
    """(document, top object, sub-name prefix) to select o by, as the tree
    selects it: from its top-level parent ("Body", "Pad."; "Assembly",
    "Joints.Joint."), so the 3D view lights the object itself and not only
    its row. An object with no parent: (document, its name, ""). A parent
    that is a link is passed over for one that is not, when there is one.
    Never raises."""
    try:
        doc, name = o.Document.Name, o.Name
    except Exception:  # noqa: BLE001
        return None
    try:
        parents = [p for p in (getattr(o, "Parents", None) or ()) if isinstance(p, tuple) and len(p) == 2]
        plain = [p for p in parents if "Link" not in str(getattr(p[0], "TypeId", ""))]
        top, sub = (plain or parents)[0] if parents else (None, "")
        if top is not None and isinstance(sub, str) and sub.endswith(name + "."):
            return doc, top.Name, sub
    except Exception:  # noqa: BLE001
        pass
    return doc, name, ""


def _add_sel(o, sub=""):
    """One object (or one of its parts: sub) added to the selection by its
    path, else by its own name. True when taken."""
    import FreeCADGui

    path = sel_path(o)
    tries = []
    if path is not None:
        tries.append((path[0], path[1], path[2] + sub))
        if path[2]:
            tries.append((path[0], o.Name, sub))
    for doc, name, s in tries:
        try:
            if s:
                FreeCADGui.Selection.addSelection(doc, name, s)
            else:
                FreeCADGui.Selection.addSelection(doc, name)
            return True
        except Exception:  # noqa: BLE001
            continue
    if not sub:
        try:
            FreeCADGui.Selection.addSelection(o)
            return True
        except Exception:  # noqa: BLE001
            pass
    return False


# A read's own selection: whether one is standing (the next read that names
# nothing puts back _last_change_sel, the names of what the last change
# selected).
_read_sel = [False]
_last_change_sel = []
# What a read names to select: ARG_KEYS and the other keys reads take.
READ_KEYS = ARG_KEYS + ("assembly", "mesh", "points", "inspection", "robot", "job", "link")
# Arguments that name a face, an edge or a vertex as "Object.Face6".
REF_KEYS = ("a", "b", "of", "refs", "ref")
SUB_HEADS = ("Face", "Edge", "Vertex")


def _ref(v):
    """(object, sub) of "Block.Face6", or None. Plain Python."""
    if not isinstance(v, str) or "." not in v:
        return None
    obj, sub = v.rsplit(".", 1)
    return (obj, sub) if obj and sub.startswith(SUB_HEADS) and sub[len(sub.rstrip("0123456789")):].isdigit() else None


def read_refs(name, args, body):
    """[(object, sub)] a read names: its arguments' "Object.Face6" refs, and
    for shape_query the found faces or edges on its body (its answer's
    items' ref). Plain Python."""
    a = args if isinstance(args, dict) else {}
    b = body if isinstance(body, dict) else {}
    out = []
    for k in REF_KEYS:
        v = a.get(k)
        for x in v if isinstance(v, list) else [v]:
            r = _ref(x)
            if r and r not in out:
                out.append(r)
    if name == "shape_query":
        on = b.get("body") or a.get("body")
        for it in b.get("items") if isinstance(b.get("items"), list) else []:
            ref = it.get("ref") if isinstance(it, dict) else it
            if isinstance(on, str) and isinstance(ref, str) and ref.startswith(SUB_HEADS):
                out.append((on, ref))
    return out[:SUBS_MOST]


def _hidden(o):
    """An object a person cannot see: its view says Visibility false (a mesh
    an add-on hid on purpose stayed selected, round 4). Objects
    with no view (a stand-in, no window) count as seen. Never raises."""
    try:
        vo = getattr(o, "ViewObject", None)
        return vo is not None and getattr(vo, "Visibility", True) is False
    except Exception:  # noqa: BLE001
        return False


def _select(objs):
    import FreeCADGui

    objs = [o for o in objs or () if not _hidden(o)]  # never a hidden object (round 6)
    if not objs:
        return
    _selected[0] += 1
    FreeCADGui.Selection.clearSelection()
    for o in objs:
        _add_sel(o)
    isolation_off(objs)


def is_joint(o):
    """An Assembly joint (FreeCAD's own test: a JointType property,
    src/Mod/Assembly/Gui/ViewProviderAssembly.cpp onSelectionChanged)."""
    try:
        return "JointType" in (getattr(o, "PropertiesList", None) or ())
    except Exception:  # noqa: BLE001
        return False


def isolation_off(objs):
    """A joint selected alone makes FreeCAD's Assembly draw every part but
    the joint's two see-through (ViewProviderAssembly::isolateJointReferences
    on the selection's AddSelection, with one assembly in the document); when
    its references do not resolve to the assembly's own parts, the whole
    assembly went see-through (asm 049). The echo selects a joint to show it
    in the tree, not to isolate it: the isolation is cleared again
    (clearIsolate, as FreeCAD's own joint dialog does when it closes). The
    labels of the assemblies cleared. Never raises."""
    done = []
    try:
        joints = [o for o in objs or () if is_joint(o)]
        if not joints:
            return done
        doc = joints[0].Document
        for a in doc.findObjects("Assembly::AssemblyObject"):
            fn = getattr(getattr(a, "ViewObject", None), "clearIsolate", None)
            if callable(fn):
                fn()
                done.append(a.Label)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (isolation off): {e}\n")
    return done


# ---- the tree and the property view brought up to the selection (round 4) -----------------

# The panels that follow the selection on a timer of their own: FreeCAD's
# property view (src/Gui/PropertyView.cpp onSelectionChanged: a single-shot
# timer, ViewParams PropertyViewTimer, 100 ms) and the tree (src/Gui/Tree.cpp
# onSelectionChanged: selectTimer, which also opens and scrolls to the row).
# Those timers fire only when the window's event loop runs that long after
# the selection; the echo selects, paints once and the next call (or the
# picture) comes first, so the property view showed an earlier call's object
# (pd 034-111, BIM 018-051) and the tree an earlier row (asm 031, points 0008).
FOLLOWERS = ("Gui::PropertyView", "Gui::TreeWidget")
_follow = []


def to_fire(rows):
    """Of rows [(owner class name, active, single shot)] for the window's
    timers, the indexes to run now: the followers' pending single-shot ones.
    Plain Python."""
    return [i for i, (cls, active, single) in enumerate(rows) if cls in FOLLOWERS and active and single]


def views_follow():
    """The tree and the property view brought up to the selection now (their
    own pending single-shot timers started again at 0 ms and run once), as
    they would be 100 ms later. How many ran. Never raises."""
    from .overlay import alive

    try:
        import FreeCADGui

        QtCore, _QtGui, _QtW = _qt()
        if not _follow or not all(alive(t) for t in _follow):
            del _follow[:]
            for t in FreeCADGui.getMainWindow().findChildren(QtCore.QTimer):
                try:
                    par = t.parent()
                    if par is not None and par.metaObject().className() in FOLLOWERS:
                        _follow.append(t)
                except RuntimeError:
                    continue
        rows = []
        for t in _follow:
            try:
                rows.append((t.parent().metaObject().className(), t.isActive(), t.isSingleShot()))
            except RuntimeError:
                rows.append(("", False, False))
        fire = to_fire(rows)
        for i in fire:
            _follow[i].start(0)
        if fire:
            flags = _paint_flags(QtCore)
            for _ in range(2):
                QtCore.QCoreApplication.processEvents(flags)
        return len(fire)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (views follow): {e}\n")
        return 0


def _select_subs(obj, subs):
    """obj's named parts selected (a sketch's new edges and constraints),
    by the path Sketcher itself selects them by (the body, then
    "Sketch.Edge3"). True when at least one was taken."""
    import FreeCADGui

    if obj is None or not subs:
        return False
    _selected[0] += 1
    FreeCADGui.Selection.clearSelection()
    got = False
    for sub in subs:
        got = _add_sel(obj, sub) or got
    return got


class _Still:
    """A view's animation off for one step, then as it was: a camera turn
    FreeCAD starts animated is cut off at its first frame by the echo's
    next fit, and the view stayed where it was."""

    def __init__(self, view):
        self.v, self.was = view, None

    def __enter__(self):
        try:
            self.was = bool(self.v.isAnimationEnabled())
            if self.was:
                self.v.setAnimationEnabled(False)
        except Exception:  # noqa: BLE001
            self.was = None
        return self

    def __exit__(self, *exc):
        if self.was:
            try:
                self.v.setAnimationEnabled(True)
            except Exception:  # noqa: BLE001
                pass
        return False


def faces_plane(direction, normal):
    """Whether a camera looking along direction faces a plane with this
    normal (from either side). Plain: (x, y, z) each."""
    try:
        d = sum(a * b for a, b in zip(direction, normal))
        ld = sum(a * a for a in direction) ** 0.5
        ln = sum(a * a for a in normal) ** 0.5
        return ld > 0 and ln > 0 and abs(d) / (ld * ln) > 0.999
    except Exception:  # noqa: BLE001
        return False


# ---- never a second task dialog (round 5) --------------------------------------------------

def foreign_task(gd=None):
    """What keeps the echo from opening or closing anything in the task
    panel, in words, or None. FreeCAD asks "A dialog is already open in the
    task panel — Close this dialog?" in a modal box when a sketch or a Part
    Design feature is opened for editing while another task dialog is open
    (src/Mod/Sketcher/Gui/ViewProviderSketch.cpp 3434-3448, src/Mod/PartDesign/
    Gui/ViewProvider.cpp 135; a sketch left open in another document counts:
    Gui::Document::setEdit resets only its own document's edit). Such a box
    stopped a batch live (round 4). Blocking: an edit the echo did not open,
    in any document; a task dialog with no edit behind it (a Part Design or
    other task a person or a tool opened). Not blocking: the echo's own sketch
    in gd's document (setEdit there closes it first, with no question).
    Never raises."""
    try:
        import FreeCADGui

        ed = edit_document()
        if ed is not None:
            obj = getattr(ed.getInEdit(), "Object", None)
            key = (ed.Document.Name, getattr(obj, "Name", None))
            if key not in _agent_edits:
                return f"{key[0]}.{key[1]} is open for editing, not by the agent"
            if gd is not None and ed is not gd and getattr(gd, "Document", None) is not ed.Document:
                return f"the agent's {key[0]}.{key[1]} is open in another document"
            return None
        if FreeCADGui.Control.activeDialog():
            return "a task dialog is open"
    except Exception:  # noqa: BLE001
        return None
    return None


def _leave_own_elsewhere(gd):
    """The echo's own sketch open in another document than gd left first, so
    opening one in gd asks nothing. True when one was left."""
    try:
        ed = edit_document()
        if ed is None or ed is gd or getattr(gd, "Document", None) is ed.Document:
            return False
        obj = getattr(ed.getInEdit(), "Object", None)
        key = (ed.Document.Name, getattr(obj, "Name", None))
        if key not in _agent_edits:
            return False
        ed.resetEdit()
        _agent_edits.discard(key)
        return True
    except Exception:  # noqa: BLE001
        return False


def enter_edit(gd, obj):
    """obj (a sketch) opened for editing as a double-click opens it, with
    the camera turned to face it at once: FreeCAD turns it itself, animated,
    and the echo's fit then cut the turn off, so the sketch was edited in
    the isometric view with the solid in front of it. If the camera still
    does not face the sketch after that, it is set to the sketch's own
    orientation. Returns what was done, for the trace. Never while a task
    dialog the echo did not open is up (foreign_task): then nothing is
    opened and the trace says why."""
    _leave_own_elsewhere(gd)
    why = foreign_task(gd)
    if why:
        return f"not opened: {why}"
    v = getattr(gd, "ActiveView", None)
    with _Still(v):
        gd.setEdit(obj.Name)
    try:
        _agent_edits.add((obj.Document.Name, obj.Name))  # opened by the agent: it may leave it (leave_agent_edit)
    except Exception:  # noqa: BLE001
        pass
    did = "opened"
    try:
        rot = obj.getGlobalPlacement().Rotation
        n = rot.multVec(FreeCAD.Vector(0, 0, 1))
        d = v.getViewDirection()
        if not faces_plane((d.x, d.y, d.z), (n.x, n.y, n.z)):
            with _Still(v):
                v.setCameraOrientation(rot)
            did = "opened, camera turned to it"
    except Exception as e:  # noqa: BLE001
        did = f"opened ({type(e).__name__} on the camera check)"
    return did


def edit_document():
    """The window's document that has something open for editing (one at
    most in FreeCAD), or None."""
    import FreeCADGui

    try:
        fn = getattr(FreeCADGui, "editDocument", None)
        ed = fn() if callable(fn) else None
        if ed is not None and ed.getInEdit() is not None:
            return ed
    except Exception:  # noqa: BLE001
        pass
    return None


# ---- a sketch the agent left open in another document (A1/S9, round 3) --------------------

# The sketches the echo itself opened for editing: (document name, object
# name). Only one of these is ever left by the echo for a call in another
# document; a sketch the person opened is never closed from here. An entry
# goes when its sketch is no longer the one in edit (closed by anyone).
_agent_edits = set()
# Calls that drive the window as a person would (a command, a menu entry,
# a click, a dialog): a sketch open then is part of that flow.
FLOWS = ("cmd_", "menu_", "gui_", "dialog_")


def edit_to_leave(name, args, call_doc, edit_doc, edit_obj, mine, flow=False):
    """Whether the echo leaves the sketch edit_obj (open in document edit_doc,
    by name) before a call that works in call_doc: only when the echo itself
    opened that edit (mine: _agent_edits), it is in another document than
    the call's, the call does not name the sketch, and no command, menu,
    click or dialog flow is running (flow, or a FLOWS call). A sketch left in
    edit keeps FreeCAD's task dialog open for the whole application, and
    every Part and Assembly button stays grey in every document. Plain
    Python."""
    if flow or not isinstance(name, str) or name.startswith(FLOWS):
        return False
    if not call_doc or not edit_doc or call_doc == edit_doc or edit_obj is None:
        return False
    if (edit_doc, getattr(edit_obj, "Name", None)) not in mine:
        return False
    a = args if isinstance(args, dict) else {}
    ids = {getattr(edit_obj, "Name", None), getattr(edit_obj, "Label", None)} - {None, ""}
    return not (ids & {n for v in a.values() for n in _names(v)})


def _flow_running():
    """A modal dialog is up (a menu's or a dialog's own loop): a flow the
    person or the agent is in the middle of."""
    try:
        _QtCore, _QtGui, QtW = _qt()
        return QtW.QApplication.activeModalWidget() is not None
    except Exception:  # noqa: BLE001
        return False


def _prune_edits():
    """_agent_edits kept to the sketch still in edit, if the echo opened it."""
    try:
        ed = edit_document()
        obj = getattr(ed.getInEdit(), "Object", None) if ed is not None else None
        key = (ed.Document.Name, obj.Name) if obj is not None else None
    except Exception:  # noqa: BLE001
        key = None
    for k in list(_agent_edits):
        if k != key:
            _agent_edits.discard(k)
    return key


def leave_agent_edit(name, args, call_doc):
    """The sketch the echo opened in another document left (resetEdit on
    that document) when edit_to_leave says so. "<doc>.<sketch>" when it was
    left, else None. Never raises."""
    try:
        key = _prune_edits()
        if key is None:
            return None
        ed = edit_document()
        obj = getattr(ed.getInEdit(), "Object", None)
        doc_name = getattr(call_doc, "Name", None)
        if not edit_to_leave(name, args, doc_name, key[0], obj, _agent_edits, _flow_running()):
            return None
        ed.resetEdit()
        _agent_edits.discard(key)
        return f"{key[0]}.{key[1]}"
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (leave edit): {e}\n")
        return None


# ---- the Sketcher's edit toolbars (round 3, item 2) ----------------------------------------

# FreeCAD 1.1.3's Sketcher toolbars shown only while a sketch is in edit
# (src/Mod/Sketcher/Gui/Workbench.cpp editModeToolbarNames). Their shown or
# hidden state is saved when a sketch is left in the Sketcher bench
# (leaveEditMode, SaveState) — a sketch closed while they were not up (the
# bench brought up while the sketch was open in another document, where
# Workbench::activated does not make them available) saves them hidden,
# and from then on no sketch shows them.
SKETCH_EDIT_BARS = ("Edit Mode", "Geometries", "Constraints", "Sketcher Tools", "B-Spline Tools", "Visual Helpers",
                    "Sketcher Edit Tools")


def bars_to_show(bars):
    """Of [(name, shown)] for the toolbars found, the names to show: all of
    the Sketcher's edit toolbars when none of them is up (a person who hides
    one or two keeps that). Plain Python."""
    found = [(n, v) for n, v in bars if n in SKETCH_EDIT_BARS]
    if not found or any(v for _n, v in found):
        return []
    return [n for n, _v in found]


def sketch_bars_shown():
    """The Sketcher's edit toolbars put up while a sketch is in edit and none
    of them shows (shown as the toolbar's own show(), as its entry in the
    toolbars' menu does). The names shown, or None. Never raises."""
    try:
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        ed = gd.getInEdit() if gd is not None else None
        if getattr(getattr(ed, "Object", None), "TypeId", "") != "Sketcher::SketchObject":
            return None
        _QtCore, _QtGui, QtW = _qt()
        bars = [b for b in FreeCADGui.getMainWindow().findChildren(QtW.QToolBar) if b.objectName() in SKETCH_EDIT_BARS]
        names = bars_to_show([(b.objectName(), b.isVisible()) for b in bars])
        for b in bars:
            if b.objectName() in names:
                b.show()
        return names or None
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (sketch toolbars): {e}\n")
        return None


# ---- the view in front: a page, a spreadsheet, the 3D view (round 3, item 4) ----------------

def _is_3d(sub):
    try:
        w = sub.widget()
        return w is not None and (w.metaObject().className() == "Gui::View3DInventor" or type(w).__name__ == "View3DInventor")
    except Exception:  # noqa: BLE001
        return False


def view_title_is(title, label):
    """Whether an MDI view's title ("Unnamed : 1[*]") is a view of the
    document labelled label. Plain Python."""
    t = str(title or "").replace("[*]", "").strip()
    return bool(label) and (t == label or t.startswith(label + " : "))


def front_3d(doc):
    """The 3D view of doc brought to the front when a drawing page or a
    spreadsheet is in front (a part_ call after a page left the page up: the
    window's active sub-window is None while FreeCAD is not the application
    in front, so the old check never saw the page). "3D view" when it was,
    else None. Never raises."""
    try:
        import FreeCADGui

        _QtCore, _QtGui, QtW = _qt()
        area = FreeCADGui.getMainWindow().findChild(QtW.QMdiArea)
        if area is None:
            return None
        cur = area.activeSubWindow() or area.currentSubWindow()
        if cur is None or _is_3d(cur):
            return None
        label = getattr(doc, "Label", None)
        subs = [s for s in area.subWindowList() if _is_3d(s)]
        mine = [s for s in subs if view_title_is(s.widget().windowTitle(), label)]
        if not mine:
            return None
        area.setActiveSubWindow(mine[0])
        return "3D view"
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (3D view to front): {e}\n")
        return None


def pages_of(objs):
    """The TechDraw pages objs are on (a page itself, else the pages that
    hold a view, a dimension or an annotation: its InList, through a group
    of views once). Never raises."""
    out = []
    for o in objs or ():
        try:
            if getattr(o, "TypeId", "") == "TechDraw::DrawPage":
                if o not in out:
                    out.append(o)
                continue
            for p in list(getattr(o, "InList", None) or ()):
                if getattr(p, "TypeId", "") == "TechDraw::DrawPage":
                    if p not in out:
                        out.append(p)
                else:
                    for q in list(getattr(p, "InList", None) or ()):
                        if getattr(q, "TypeId", "") == "TechDraw::DrawPage" and q not in out:
                            out.append(q)
        except Exception:  # noqa: BLE001
            continue
    return out


def is_sheet(o):
    """A spreadsheet, FreeCAD's own or one derived from it (Assembly's
    Bills_of_Materials is an Assembly::BomObject, a Spreadsheet::Sheet: the
    old test by TypeId never opened it, asm 055)."""
    try:
        if getattr(o, "TypeId", "") == "Spreadsheet::Sheet":
            return True
        return bool(o.isDerivedFrom("Spreadsheet::Sheet"))
    except Exception:  # noqa: BLE001
        return False


def sheet_refs(name, args, body):
    """The names of the spreadsheet a call worked in: its answer's or its
    arguments' sheet (or bom), the sheet part of a parameter's ref
    ("Params.width"), and for the param_ tools the Params sheet. Plain
    Python."""
    a = args if isinstance(args, dict) else {}
    b = body if isinstance(body, dict) else {}
    out = []
    for v in (b.get("sheet"), a.get("sheet"), b.get("bom")):
        if isinstance(v, str) and v:
            out.append(v)
    ref = b.get("ref")
    if isinstance(ref, str) and "." in ref:
        out.append(ref.split(".", 1)[0])
    if str(name).startswith("param_"):
        out.append("Params")
    return list(dict.fromkeys(out))


def front_view_of(o):
    """o's view already open (a page's, a sheet's, a text's tab) brought to
    the front, by its title; nothing is opened. Its label, or None."""
    try:
        import FreeCADGui

        _QtCore, _QtGui, QtW = _qt()
        area = FreeCADGui.getMainWindow().findChild(QtW.QMdiArea)
        label = getattr(o, "Label", None)
        for sub in area.subWindowList() if area is not None else []:
            w = sub.widget()
            if w is not None and not _is_3d(sub) and view_title_is(w.windowTitle(), label):
                area.setActiveSubWindow(sub)
                return label
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (front view of {getattr(o, 'Label', '?')}): {e}\n")
    return None


def show_view_of(o, read=False):
    """o's own view brought to the front (a page, a spreadsheet, a text: what
    a double-click on its tree row opens). Its label, or None. For a read,
    or while a task dialog the echo did not open is up, only a view already
    open is brought up (front_view_of): a double-click runs the object's own
    code (a sheet's switches the workbench), and a read never starts
    anything (round 5)."""
    if read or foreign_task():
        return front_view_of(o)
    vo = getattr(o, "ViewObject", None)
    if vo is None:
        return None
    try:
        if is_sheet(o) and callable(getattr(vo, "showSheetMdi", None)):
            # A sheet's own tab, opened as its view provider's setEdit opens
            # it (ViewProviderSheet::showSheetMdi, src/Mod/Spreadsheet/Gui/
            # ViewProviderSpreadsheet.cpp 100-107), with no double-click: an
            # Assembly BOM's double-click opens its "Bill of Materials" task
            # dialog in place of the table (ViewProviderBom::doubleClicked,
            # src/Mod/Assembly/Gui/ViewProviderBom.cpp 53-66), which stayed
            # open in every later picture (round 4, asm 055 on).
            vo.showSheetMdi()
            return o.Label
        if is_sheet(o):
            return front_view_of(o)  # never a sheet's double-click (a BOM's opens a task dialog)
        had = _dialog_up()
        vo.doubleClicked()
        if not had and _dialog_up():
            note_own_dialog(o)
        return o.Label
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (view of {getattr(o, 'Label', '?')}): {e}\n")
        return None


# A task dialog the echo itself opened (a double-click that opened one):
# (document name, object name, the dialog's content titles). Closed at the
# start of the next call that is not a look at the window, and only while it
# is still that dialog and nothing is in edit (round 6, item 7). A dialog a
# person or a tool opened is never closed from here.
_own_dialog = [None]


def _dialog_up():
    try:
        import FreeCADGui

        return bool(FreeCADGui.Control.activeDialog())
    except Exception:  # noqa: BLE001
        return False


def _dialog_key():
    """The open task dialog's content titles (its widgets' window titles),
    to tell it again; () when none can be read. Never raises."""
    try:
        import FreeCADGui

        dlg = FreeCADGui.Control.activeTaskDialog()
        if dlg is None:
            return None
        out = []
        for w in dlg.getDialogContent() or ():
            try:
                out.append(str(w.windowTitle()))
            except Exception:  # noqa: BLE001
                out.append("?")
        return tuple(out)
    except Exception:  # noqa: BLE001
        return ()


def note_own_dialog(o):
    """The task dialog up now was opened by the echo (for o)."""
    try:
        _own_dialog[0] = (o.Document.Name, o.Name, _dialog_key())
    except Exception:  # noqa: BLE001
        _own_dialog[0] = (None, None, _dialog_key())


def close_own_dialog():
    """The task dialog the echo opened closed, when it is still up, still
    the same one, and nothing is in edit. Its object's name, or None. Never
    raises."""
    rec, _own_dialog[0] = _own_dialog[0], None
    if rec is None:
        return None
    try:
        import FreeCADGui

        if not _dialog_up() or edit_document() is not None:
            return None
        if rec[2] is not None and _dialog_key() != rec[2]:
            return None  # another dialog since: not the echo's
        FreeCADGui.Control.closeDialog()
        return rec[1] or "dialog"
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (own dialog): {e}\n")
        return None


def _workbench_for(name):
    """The bench for a tool: the longest WORKBENCH key that is its name or
    a prefix of it (core's prefixes and what add-ons declared)."""
    return _longest(name, WORKBENCH)


# Declared benches not loaded in this window, logged once each.
UNKNOWN_BENCHES = set()


def bench_to_switch(name, loaded, active):
    """The bench to bring up for this call, or None: none declared, already
    in front, or not loaded in this window (an add-on's bench when the
    add-on is not here) — that last logged once, never an error."""
    wb = _workbench_for(name)
    if not wb or wb == active:
        return None
    if wb not in loaded:
        if wb not in UNKNOWN_BENCHES:
            UNKNOWN_BENCHES.add(wb)
            if FreeCAD is not None:
                FreeCAD.Console.PrintLog(f"Agent Link echo: {wb} (for {name}) is not loaded here; the bench stays as it is.\n")
        return None
    return wb


def bench_ready(wb):
    """Before a workbench is brought up from here: what must be in place so
    its first start cannot stop the window. OpenSCAD's start looks for the
    OpenSCAD program when FreeCAD's preference for it is empty — on a Mac by
    asking Finder through AppleScript, with no time limit, behind a permission
    prompt (FreeCAD 1.1: src/Mod/OpenSCAD/InitGui.py, OpenSCADUtils.py): the
    plain search is put in its place first. Never raises."""
    if wb != "OpenSCADWorkbench":
        return
    try:
        from .families import openscad

        openscad.plain_search()
    except Exception as e:  # noqa: BLE001
        if FreeCAD is not None:
            FreeCAD.Console.PrintLog(f"Agent Link: OpenSCAD's search was not replaced ({e})\n")


def _edited(gd):
    """The object open for editing in the window's document gd, or None."""
    ed = gd.getInEdit() if gd is not None else None
    return getattr(ed, "Object", None) if ed is not None else None


def _on():
    """The echo is on: a FreeCAD with its window, and Echo not switched
    off. False (never an error) without FreeCAD or its window."""
    try:
        return bool(enabled())  # FreeCAD.GuiUp first: no window, no echo
    except Exception:  # noqa: BLE001
        return False


def _plog(text):
    try:
        FreeCAD.Console.PrintLog(text)
    except Exception:  # noqa: BLE001
        pass


# Tools that make a sketch: it is opened for editing once made.
NEW_SKETCH = ("sketch_new", "sketch_mirror", "sketch_merge")
# Calls that never close what is open for editing: they work inside the
# sketch (or the window) as the person would, with it open — a command, a
# menu entry, a click or a dialog acts in the mode the window is in (closing
# the sketch first left Sketcher_LeaveSketch greyed out and refused).
KEEP_EDIT = ("sketch_", "view_", "note_", "measure", "cmd_", "menu_", "gui_", "dialog_", "window_", "selection",
             "steps_", "history_", "workbench", "doc_save", "snapshot_")
# Calls that build on a sketch: a person leaves the sketch first.
BUILDS_ON = ("pd_", "part_", "feature_", "body_")


def _names(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple)):
        return [x for x in v if isinstance(x, str)]
    return []


def closes_edit(name, args, obj):
    """Whether a call closes what is open for editing (obj, a sketch)
    first. Never for a call in KEEP_EDIT, and never for one that names obj
    in its arguments and does not build on it (object_set on the sketch,
    a lesson's own call): the echo never closes a sketch the call works in.
    Plain Python."""
    if not isinstance(name, str) or name.startswith(KEEP_EDIT):
        return False
    if name.startswith(BUILDS_ON):
        return True
    a = args if isinstance(args, dict) else {}
    mine = {getattr(obj, "Name", None), getattr(obj, "Label", None)} - {None, ""}
    named = {n for v in a.values() for n in _names(v)}
    return not (mine & named)


def read_words(what, result):
    """A read's words: what it did, then what came of it ("Checked
    CrankSlider for overlaps: clear"), unless that adds nothing."""
    what = str(what or "").strip()
    r = str(result or "").strip()
    if not r or r == "Done" or r.lower() in what.lower():
        return what
    from . import activity

    return f"{what}: {activity._lower(r)}"


def refused_words(what, result):
    """A refused call's words ("Cut a groove: refused (…)")."""
    r = str(result or "").strip()
    why = r[len("Refused:"):].strip() if r.startswith("Refused:") else ""
    return f"{what}: refused" + (f" ({why})" if why else "")


# ---- a CAM operation's path shown, as CAM's own GUI shows it (round 4) ----------------------

def is_path_op(o):
    """A CAM operation or dressup (it has a Path; a Job has Operations)."""
    try:
        props = getattr(o, "PropertiesList", None) or ()
        return "Path" in props and "Operations" not in props and "Stock" not in props
    except Exception:  # noqa: BLE001
        return False


def _jobs(doc):
    try:
        return [o for o in doc.Objects if "Operations" in (getattr(o, "PropertiesList", None) or ()) and "Stock" in o.PropertiesList]
    except Exception:  # noqa: BLE001
        return []


def cam_shown(doc, objs, job_ref=None):
    """What CAM's own GUI does when it makes an operation and edits a job
    (src/Mod/CAM/Path/Op/Gui/Base.py Create: the operation's
    ViewObject.Visibility = True — CAM's App-side Create, which the tools
    use, leaves it hidden, so no toolpath was ever drawn: cam 008-032;
    Path/Main/Gui/Job.py rememberBaseVisibility: the job's model clone
    shown, the original body hidden, the stock shown), done here as view
    state: the operations named shown, the stock see-through. The labels
    shown. Never raises."""
    done = []
    try:
        ops = [o for o in objs or () if is_path_op(o)]
        jobs = [o for o in _objects(doc, [job_ref]) if o in _jobs(doc)] if isinstance(job_ref, str) else []
        if not jobs:
            alls = _jobs(doc)
            jobs = [j for j in alls if any(op in (getattr(j.Operations, "Group", None) or ()) or j in
                                           (getattr(op, "InListRecursive", None) or ()) for op in ops)] or (alls if len(alls) == 1 else [])
        for j in jobs:
            for base in list(getattr(getattr(j, "Model", None), "Group", None) or ()):
                try:
                    orig = j.Proxy.baseObject(j, base)
                    if orig is not None and orig is not base and _seen(orig):
                        orig.ViewObject.Visibility = False
                        done.append(f"{orig.Label} hidden")
                    if not _seen(base):
                        base.ViewObject.Visibility = True
                except Exception:  # noqa: BLE001
                    continue
            stock = getattr(j, "Stock", None)
            vo = getattr(stock, "ViewObject", None) if stock is not None else None
            if vo is not None:
                vo.Visibility = True
                if int(vo.Transparency or 0) < 70:
                    vo.Transparency = 70
            # Round 6: the model clone in front of the path made see-through
            # (put back at the next change, as any cover), so the path is
            # not behind an opaque block (cam 008-032).
            for base in list(getattr(getattr(j, "Model", None), "Group", None) or ()):
                try:
                    bvo = base.ViewObject
                    if _seen(base) and int(bvo.Transparency or 0) < COVER_ALPHA:
                        _covers.append((base.Document.Name, base.Name, int(bvo.Transparency or 0)))
                        bvo.Transparency = COVER_ALPHA
                        done.append(f"{base.Label} see-through")
                except Exception:  # noqa: BLE001
                    continue
        for op in ops:
            if not _seen(op):
                op.ViewObject.Visibility = True
                done.append(op.Label)
            # FreeCAD draws a path 1 px wide in dark green by default
            # (src/Mod/CAM/Gui/ViewProviderPath.cpp 153-165, DefaultPathLineWidth
            # 1): drawn 3 px wide until the next change.
            if set_view_prop(op, "LineWidth", PATH_WIDTH, at_least=True):
                done.append(f"{op.Label} {PATH_WIDTH:g} px")
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (CAM path shown): {e}\n")
    return done


PATH_WIDTH = 3.0
# View properties the echo set for a call (document, object, property, value
# it had): put back at the next changing call (scene_clear).
_view_props = []


def set_view_prop(o, prop, value, at_least=False):
    """o's view property set (to at least value), noted to be put back.
    True when changed. Never raises."""
    try:
        vo = o.ViewObject
        if prop not in (getattr(vo, "PropertiesList", None) or ()):
            return False
        old = getattr(vo, prop)
        if (at_least and old >= value) or old == value:
            return False
        _view_props.append((o.Document.Name, o.Name, prop, old))
        setattr(vo, prop, value)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---- a FEM result coloured, as FreeCAD's own result panel colours it (round 4) -------------

FEM_RESULT_TOOLS = ("fea_solve", "fea_native")


def fem_result_shown(doc, body, session=None):
    """A strength result shown in colour in the window (round 6, item 2;
    fem 030, 034: none was ever seen).

    FreeCAD's own result, where the solve kept one (fea_solve by FreeCAD's
    FEM route, fea_native run): coloured by von Mises with femresult.
    resulttools.show_result (the Results panel's choice:
    setNodeColorByScalars on the result's own mesh, which it shows). The
    importer leaves that mesh hidden and the post pipeline, the study's
    solid and its FEM mesh shown (src/Mod/Fem/feminout/importCcxFrdResults.py
    100-111), all on the same surface: the colours were under them. Those are
    hidden now while the colours stand (view state, shown again at the next
    changing call: scene_clear).

    Agent Link's own deck keeps no FEM object (its answer says "kept"): the
    last solve's field (session._agentlink_fea) is drawn as the stress map
    view_render draws (render.MAPS["stress"]), on a mesh in the 3D view's
    scene only, with the body hidden under it.

    What was shown, or None. Never raises."""
    try:
        b = body if isinstance(body, dict) else {}
        named = [o for o in _objects(doc, [b.get("analysis")]) if getattr(o, "TypeId", "") == "Fem::FemAnalysis"]
        analyses = named or [o for o in doc.Objects if getattr(o, "TypeId", "") == "Fem::FemAnalysis"]
        results = [o for an in analyses for o in (getattr(an, "Group", None) or ())
                   if str(getattr(o, "TypeId", "")).startswith("Fem::FemResultObject") and getattr(o, "Mesh", None) is not None
                   and len(getattr(o, "vonMises", None) or ()) > 0]
        if results and not (isinstance(b.get("solvedBy"), str) and "own CalculiX deck" in b["solvedBy"]):
            res = results[-1]
            from femresult import resulttools

            resulttools.show_result(res, "Sabs")
            an = next((a for a in analyses if res in (getattr(a, "Group", None) or ())), None)
            hide = []
            for o in list(getattr(an, "Group", None) or ()) if an is not None else []:
                t = str(getattr(o, "TypeId", ""))
                if o is res.Mesh or o is res:
                    continue
                if t.startswith("Fem::FemMeshObject") or t.startswith("Fem::FemPostPipeline"):
                    hide.append(o)
                    part = getattr(o, "Shape", None) if t.startswith("Fem::FemMeshObject") else None
                    if part is not None and hasattr(part, "TypeId"):
                        hide.append(part)
            hid = hide_for_scene(hide)
            return {"result": res.Label, "hidden": hid}
        r = getattr(session, "_agentlink_fea", None) if session is not None else None
        if not r or "field" not in r:
            return None
        from . import render

        fn = (render.MAPS.get("stress") or (None,))[0]
        if fn is None:
            return None
        m = fn(session, {"detail": 20000})
        layer = (m.get("layers") or [None])[0]
        if not layer:
            return None
        import numpy as np

        vals = np.asarray(layer["values"], dtype=float)
        fin = vals[np.isfinite(vals)]
        if not len(fin):
            return None
        lo, hi = float(np.percentile(fin, 1)), float(np.percentile(fin, 99))
        lo = min(0.0, float(fin.min())) if lo >= 0 else lo
        if hi <= lo:
            hi = lo + 1e-6
        cols = render.colours_for(vals, lo, hi, m.get("cmap", "jet"))
        drawn = scene_field(layer["V"], layer["F"], cols)
        if not drawn:
            return None
        return {"map": "stress (Agent Link's own solve)", "range": [round(lo, 3), round(hi, 3)], "triangles": drawn}
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (FEM result): {e}\n")
        return None


# ---- a later change puts away the inspection colours (round 4) -----------------------------

# Inspection results the agent made, by document: hidden (view state) at the
# next changing call that is not an inspection call — their colour map and
# legend covered later results (core 0071-0097).
_inspections = {}


def inspections_after(doc, name, made):
    """Note the inspection results this call made; for a changing call of
    another family, hide those noted (the legend goes with them:
    ViewProviderInspection::hide). The names hidden. Never raises."""
    hidden = []
    try:
        key = doc.Name
        if str(name).startswith("insp_"):
            new = [o.Name for o in made or () if getattr(o, "TypeId", "") == "Inspection::Feature"]
            if new:
                _inspections.setdefault(key, [])
                _inspections[key] += [n for n in new if n not in _inspections[key]]
            return hidden
        for n in _inspections.pop(key, []):
            o = doc.getObject(n)
            vo = getattr(o, "ViewObject", None) if o is not None else None
            try:
                if vo is not None and vo.Visibility:
                    vo.Visibility = False
                    hidden.append(n)
            except Exception:  # noqa: BLE001
                continue
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (inspections): {e}\n")
    return hidden


# ---- a feature's sketch put away, as FreeCAD's own commands do (round 4) --------------------

def _linked(v):
    """The object of a link property's value (obj, (obj, subs), [(obj,
    subs)]), or None."""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    return v


def profiles_hidden(made):
    """The sketch a Part Design feature was made from hidden once the
    feature is made, as FreeCAD's own Pad, Pocket, Revolution … do
    (src/Mod/PartDesign/Gui/Command.cpp finishProfileBased: FCMD_OBJ_HIDE
    on the profile): the Master outline stayed drawn over Tut from pd 007
    on. View state only. The names hidden. Never raises."""
    hidden = []
    for o in made or ():
        try:
            if "Profile" not in (getattr(o, "PropertiesList", None) or ()) or not _has_solid(o):
                continue
            prof = _linked(o.Profile)
            if getattr(prof, "TypeId", "") != "Sketcher::SketchObject" or not _seen(prof):
                continue
            prof.ViewObject.Visibility = False
            hidden.append(prof.Name)
        except Exception:  # noqa: BLE001
            continue
    return hidden


# ---- the words of a change: what it made and its key value (round 4) ------------------------

def change_words(what, body):
    """A change's words with the answer's key value (a volume, a length, a
    count, a file) when the words do not give it yet ("Padded Profile by 53
    mm" stays; "Made a mesh" becomes "Made a mesh: 152 facets"). Plain
    Python."""
    from . import activity

    what = str(what or "")
    try:
        v = activity.key_value(body)
    except Exception:  # noqa: BLE001
        v = None
    if not v or v.lower() in what.lower():
        return what
    return f"{what}: {v}"


class Echo:
    def __init__(self, session):
        self.s = session
        self.t0 = None
        # How the call in hand is shown (pace()): set in before, used by
        # after and the waits between.
        self.mode, self.ms = "full", None

    def _pace(self, tool):
        """This call's pace, from where its batch is (session.batch_now)."""
        try:
            self.mode, self.ms = pace(getattr(self.s, "batch_now", None), bool(getattr(tool, "changes", False)), delay_ms(), batch_delay_ms())
        except Exception:  # noqa: BLE001 - a preference that cannot be read: the full pace
            self.mode, self.ms = "full", None

    def _pause(self):
        """The pause of the call in hand."""
        _wait(delay_ms() if self.ms is None else self.ms)

    def live(self):
        """Shown in the window, unless an extension asks for the window to
        be left alone (session.window_quiet, agentlink/ext.py)."""
        return not getattr(self.s, "window_quiet", False)

    def quiet(self):
        """A panel's own refresh (Panel._call quiet=True): not the agent's
        work, so nothing shown and nothing in Activity."""
        return bool(getattr(self.s, "quiet_call", False))

    def _trace(self, name):
        """This call's trace (session.echo_trace): what the echo did and
        what it could not, for a live check (session_state shows it)."""
        tr = {"tool": name}
        self.tr = tr
        try:
            self.s.echo_trace = tr
        except Exception:  # noqa: BLE001
            pass
        return tr

    def _where(self):
        """" (in <document>)" when the agent works in a document that is not
        the one in front (K), else ""."""
        try:
            if FreeCAD.ActiveDocument is not None and self.s.doc is not None and FreeCAD.ActiveDocument.Name != self.s.doc.Name:
                return f" (in {self.s.doc.Label})"
        except Exception:  # noqa: BLE001
            pass
        return ""

    def before(self, tool, args):
        self.t0 = time.time()
        self.mode, self.ms = "full", None
        self.tr = {}
        self._names0 = self._doc0 = None
        self._front_other = False
        if self.quiet():
            return
        if tool is None or skipped(tool.name) or watching(tool.name):
            # A look at the window or the session (a picture, session_state):
            # the last change's ring, words, selection and trace stay as
            # they are, so that look shows them (session_state reads the
            # trace: emptied here, it always read None).
            return
        try:
            self.s.echo_trace = None  # never the last call's
        except Exception:  # noqa: BLE001
            pass
        if not _on() or not self.live():
            return
        tr = self._trace(tool.name)
        # A task dialog the echo's own double-click opened for the last call
        # closed now, before anything else looks at the task panel (round 6).
        self._step(tr, "ownDialogClosed", close_own_dialog)
        args = args if isinstance(args, dict) else {}
        changing = bool(getattr(tool, "changes", False))
        if changing:
            # What the last change showed, put out now that another change
            # comes: its lit button (held until here), the covers made
            # see-through for its result. A read leaves them (round 3).
            rings_off()
            self._step(tr, "coversBack", restore_covers)
            self._step(tr, "sceneCleared", scene_clear)
            # A sketch the agent left open in another document greys every
            # Part and Assembly button: left first (A1/S9, round 3).
            self._step(tr, "leftEdit", leave_agent_edit, tool.name, args, self.s.doc)
            try:
                self._names0 = self._names_now()
            except Exception:  # noqa: BLE001
                self._names0 = None
        switch = switches_bench(tool)
        shown = switch or tool.name.startswith(SHOWN)
        if not shown:
            return
        self._pace(tool)
        short = self.mode == "short"
        try:
            import FreeCADGui

            wb = None
            held = foreign_task() if switch else None
            if held:
                tr["held"] = held  # no bench switch, no edit opened or closed (round 5)
            if switch and not held:
                act = FreeCADGui.activeWorkbench()
                wb = bench_to_switch(tool.name, FreeCADGui.listWorkbenches(), act.name() if act else None)
                if wb:
                    bench_ready(wb)
                    FreeCADGui.activateWorkbench(wb)
                try:
                    if not held:
                        self._mode(tool.name, args)
                except Exception as e:  # noqa: BLE001  (the words still come)
                    tr["modeError"] = f"{type(e).__name__}: {e}"
                if tool.name.startswith("sketch_"):
                    self._step(tr, "sketchBars", sketch_bars_shown)
            say(_describe(tool.name, args, None, getattr(tool, "activity", None)), where=self._where())
            cmd = command_for(tool.name, args) if switch else None
            if cmd and not changing:
                # A read that opens its panel lights its own button: the last
                # change's ring goes first, one ring at a time (an
                # add-on's reads showed two, round 4).
                rings_off()
            if cmd:
                # settle: after a bench switch its toolbars must exist before
                # a button can light — kept at the short pace too (one
                # paint, and only when the bench did switch): without it the
                # button would not light at all.
                tr["button"] = [cmd, flash_command(cmd, settle=bool(wb))]
            _select(_objects(self.s.doc, [args.get(k) for k in ARG_KEYS if args.get(k)]))
            if not switch:
                # A read that shows something (a view, a measure): its words
                # and selection are painted by the call itself and the
                # paints after it; no pause of its own.
                return
            if short and self.ms > 0:
                self._pause()  # its paints show the selection and the lit button
            else:
                _paint()
                if not short:
                    self._pause()
        except Exception as e:
            tr["beforeError"] = f"{type(e).__name__}: {e}"
            _plog(f"Agent Link echo (before {tool.name}): {e}\n")

    def _names_now(self):
        """The names of the agent's document's objects, when it is the one in
        front (what a changing call made is told from them after it: many
        tools' answers name their result under a key of their own, or not
        at all)."""
        doc = self.s.doc
        if doc is None or FreeCAD.ActiveDocument is None or FreeCAD.ActiveDocument.Name != doc.Name:
            return None
        objs = list(doc.Objects)
        self._doc0 = doc.Name
        return {o.Name for o in objs} if len(objs) <= NEW_LOOK_MOST else None

    def _views(self, name, args, body, made=()):
        """The window a person would be looking at: a TechDraw tool's page
        open in its tab; a spreadsheet a call made or filled open in its
        tab (sheet_ tools, a BOM, a BIM schedule); everything else in the
        3D view of the agent's document, brought back to the front when a
        page or a sheet was (a part_ call after a page left the page up); a
        FEM analysis made active. What was brought up, for the trace."""
        doc = self.s.doc
        page_ref = (body or {}).get("page") or (args or {}).get("page")
        if name.startswith(tuple(PAGES)):
            page = _objects(doc, [page_ref]) if isinstance(page_ref, str) else []
            page = page or [o for o in made if getattr(o, "TypeId", "") == "TechDraw::DrawPage"]
            # A call that names only its view (td_cosmetic, td_lines: td 052,
            # 053 left the 3D view in front after shape_query): the page the
            # view is on.
            page = page or pages_of(list(made) + _objects(doc, [(body or {}).get("view"), (args or {}).get("view")]))
            return show_view_of(page[0]) if page else None
        sheet = [o for o in made if is_sheet(o)]
        if not sheet and name.startswith(SHEET_TOOLS):
            sheet = [o for o in _objects(doc, sheet_refs(name, args, body)) if is_sheet(o)]
        if sheet and name.startswith(SHEET_TOOLS):
            return show_view_of(sheet[0])
        text = [o for o in made if getattr(o, "TypeId", "") == "App::TextDocument"]
        if text:
            return show_view_of(text[0])  # the text in its own tab, as a double-click opens it (core 0028)
        page = [o for o in made if getattr(o, "TypeId", "") == "TechDraw::DrawPage"]
        if page:
            return show_view_of(page[0])
        an = (body or {}).get("analysis")
        if an:
            obj = _objects(doc, [an])
            if obj:
                try:
                    import FemGui

                    FemGui.setActiveAnalysis(obj[0])
                except Exception:
                    pass
        got = front_3d(doc)
        self._container(name, args or {}, body or {}, made)
        return got

    def _container(self, name, args, body, made=()):
        """What a person would have made active for the work: an assembly
        (as Assembly's "Activate assembly" does, its joints then going into
        it), a BIM level or building (the active container new BIM objects
        go into), a CAM job's operation shown with its stock; a joint's two
        faces lit."""
        import FreeCADGui

        doc = self.s.doc
        gd = FreeCADGui.ActiveDocument
        view = getattr(gd, "ActiveView", None) if gd else None
        if view is None:
            return
        if foreign_task():
            return  # nothing made active while a task dialog the echo did not open is up (round 5)
        if name.startswith("asm_"):
            asm = _objects(doc, [body.get("assembly") or args.get("assembly")])
            if asm:
                try:
                    if view.getActiveObject("part") is not asm[0]:
                        view.setActiveObject("part", asm[0])
                except Exception:
                    pass
            if name == "asm_joint":
                ends = [body.get("a"), body.get("b")]
                lit = []
                for end in ends:
                    if not isinstance(end, str) or "." not in end:
                        continue
                    label, el = end.rsplit(".", 1)
                    o = _objects(doc, [label])
                    if o:
                        lit.append((o[0], el))
                if lit:
                    FreeCADGui.Selection.clearSelection()
                    for o, el in lit:
                        try:
                            FreeCADGui.Selection.addSelection(o, el)
                        except Exception:
                            pass
                    # The joint's two faces lit for the pause; at a batch's
                    # short pace they stay lit and the call's last paint
                    # shows them.
                    if self.mode != "short":
                        self._pause()
        elif name.startswith("cam_"):
            refs = [body.get(k) for k in ("op", "dressup", "object") if isinstance(body.get(k), str)]
            refs += [args.get(k) for k in ("op",) if isinstance(args.get(k), str)]
            shown = cam_shown(doc, list(made) + _objects(doc, refs), body.get("job") or args.get("job"))
            if shown and isinstance(getattr(self, "tr", None), dict):
                self.tr["camShown"] = shown
        # BIM: no level or building is made active here any more. BIM's own
        # tools never activate one (only a double-click or the Active entry
        # does: src/Mod/BIM/ArchBuildingPart.py activate), and the active
        # one stays highlighted for good ("House" green from bim 024 to 068).

    def _mode(self, name, args):
        """The mode a person would be in: a sketch's tools work with the
        sketch open in the Sketcher, the camera facing it; a tool that
        builds on it (a pad) closes it first, as a person leaves the sketch
        before pressing Pad. Never closed: for a call that works inside the
        sketch or the window (closes_edit), and never a sketch open in
        another document (A1/S9: left as the person or a lesson has it)."""
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        if gd is None:
            return
        editing = gd.getInEdit()
        sk = args.get("sketch") if name.startswith("sketch_") and name not in ("sketch_new", "sketch_state") else None
        found = _objects(self.s.doc, [sk]) if sk and self.s.doc is not None else []
        target = found[0] if found else None
        if target is not None:
            if editing is None or editing.Object is not target:
                self.tr["edit"] = enter_edit(gd, target)
        elif editing is not None and closes_edit(name, args, getattr(editing, "Object", None)):
            key = (gd.Document.Name, getattr(getattr(editing, "Object", None), "Name", None))
            if key not in _agent_edits:
                # Never the person's own edit: closing it is theirs to do.
                self.tr["edit"] = "left open: not opened by the agent"
                return
            # FreeCAD turns the camera back to where it was before the
            # sketch, animated. Inside a batch the next fit cut that turn off
            # at its first frame and the view stayed flat on the sketch: the
            # turn is made at once there (animation off for this one step).
            v = None
            if getattr(self.s, "batch_now", None):
                v = getattr(gd, "ActiveView", None)
            with _Still(v):
                gd.resetEdit()
            _prune_edits()
            self._left_sketch = True
            self.tr["edit"] = "closed for this call"

    def after(self, tool, args, reply):
        if self.quiet():
            return
        name = tool.name if tool is not None else "?"
        ok = not (reply or {}).get("isError")
        try:
            import json

            body = json.loads(reply["content"][0]["text"]) if reply and reply.get("content") else {}
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        what, result = None, ""
        if name != "batch":
            from . import activity

            try:
                what = activity.did(name, args, body, getattr(tool, "activity", None))
                result = activity.outcome(name, ok, body, args)
                call = activity.raw_call(name, args)
            except Exception as e:  # the words never stop a call
                what, result, call = name, "" if ok else "Refused", name
                _plog(f"Agent Link activity words ({name}): {e}\n")
            # An add-on's own words, with what it measured (WORDS: round 6):
            # in place of the echo's, here and in the Activity row.
            own = declared_words(name, args, body) if ok else None
            self._own_words = bool(own)
            if own:
                what, result = own, ""
            _note({"time": datetime.datetime.now().strftime("%H:%M:%S"), "tool": name, "ok": ok, "what": _tag(self.s) + what,
                   "result": result, "call": call, "ms": int((time.time() - (self.t0 or time.time())) * 1000)})
        if name == "batch" or tool is None or skipped(name) or watching(name):
            return
        if not _on() or not self.live():
            return
        tr = getattr(self, "tr", None)
        if not isinstance(tr, dict) or tr.get("tool") != name:
            tr = self._trace(name)
        try:
            self._after(tool, name, args if isinstance(args, dict) else {}, body, ok, what or did_name(name), result, tr)
        except Exception as e:  # noqa: BLE001  (never into the call)
            tr["afterError"] = f"{type(e).__name__}: {e}"
            _plog(f"Agent Link echo (after {name}): {e}\n")

    def _step(self, tr, key, fn, *a):
        """One part of the echo after a call, on its own: a failure in it is
        noted in the trace and the log, and the rest still runs (the words
        last of all: a failing step before them left pd_groove with no words
        and no selection at all, N3)."""
        try:
            got = fn(*a)
            if got not in (None, False, [], ""):
                tr[key] = got
            return got
        except Exception as e:  # noqa: BLE001
            tr[key + "Error"] = f"{type(e).__name__}: {e}"
            _plog(f"Agent Link echo ({key}, {tr.get('tool')}): {e}\n")
            return None

    def _after(self, tool, name, args, body, ok, what, result, tr):
        where = self._where()
        if not ok:
            # The words before the call said what was to be done: now that
            # it was refused, they say so (nothing else is shown).
            self._step(tr, "words", say, refused_words(what, result), HOLD_MS, where)
            return
        if not tool.changes:
            # A read, a check or an export: its own words and what came of
            # it, in place of the last change's (A3, N2, S8), and what it
            # read selected. The last change's ring stays lit.
            self._step(tr, "words", say, read_words(what, result), HOLD_MS, where)
            self._step(tr, "readShown", self._read_shown, name, args, body)
            if name in READ_MAPS:
                # A read whose answer is a map (curvature): drawn on the model
                # in the scene only, put away at the next change (round 6).
                self._step(tr, "mapShown", map_shown, self.s, READ_MAPS[name], args)
            return
        import FreeCADGui

        doc = self.s.doc
        # The window's view effects only where the agent's document is the
        # one in front (K): the person's own document is left alone.
        if FreeCAD.ActiveDocument is None or doc is None or FreeCAD.ActiveDocument.Name != doc.Name:
            self._step(tr, "words", say, what, HOLD_MS, where)
            _paint()
            return
        # (Objects are kept out of the trace: it goes into a batch's answer
        # as JSON; their names go in.)
        try:
            named = _objects(doc, out_names(name, args, body))
        except Exception as e:  # noqa: BLE001
            named = []
            tr["namedError"] = f"{type(e).__name__}: {e}"
        made, how = result_of(named), "answer"
        own = declared_selection(name, args, body, doc)
        if own:
            # The add-on says what its call is about (SELECTS_FOR: the scan's
            # own mesh, not the hidden one it was read from).
            got = [o for o in _objects(doc, own) if not _hidden(o)]
            if got:
                made, how = got, "declared"
        if not made:
            # An answer that names nothing (or under a key of its own): what
            # is new in the document, else what the call worked on.
            try:
                made, how = self._new_objects(doc), "new"
            except Exception as e:  # noqa: BLE001
                made, how = [], "new"
                tr["newObjectsError"] = f"{type(e).__name__}: {e}"
        if not made:
            made, how = [o for o in _objects(doc, [args.get(k) for k in ARG_KEYS if args.get(k)])], "worked on"
        tr["made"] = [getattr(o, "Name", "?") for o in made]
        if made:
            tr["madeFrom"] = how
        self._front_other = bool(self._step(tr, "views", self._views, name, args, body, made)) and name.startswith(tuple(PAGES) + SHEET_TOOLS)
        gd = FreeCADGui.ActiveDocument
        # A tool that makes a sketch opens it (S5: a mirror or a merge
        # showed the old one), the camera facing it.
        if name in NEW_SKETCH and gd is not None:
            self._step(tr, "edit", self._open_new_sketch, gd, made)
        if name == "sketch_attach" and gd is not None:
            # Put on another plane while open: opened again, so the camera
            # faces the plane it is on now (sk 053 was seen edge-on).
            self._step(tr, "edit", self._reopen_sketch, gd, args)
        if name.startswith("sketch_"):
            self._step(tr, "sketchBars", sketch_bars_shown)
        # Part Design bodies left showing their tip (P4).
        if name.startswith(("pd_", "feature_", "sketch_attach")):
            self._step(tr, "tipShown", lambda: [b.Name for b in bodies_of(doc, args, body, named) if tip_shown(b)])
        self._step(tr, "datumsHidden", datums_after, doc, named)
        if name == "asm_explode" and args.get("collapse") is True:
            self._step(tr, "explodeLinesOff", explode_lines_off, doc)
        sketch = None
        if name.startswith("sketch_"):
            try:
                sketch = _edited(gd)
            except Exception as e:  # noqa: BLE001
                tr["inEditError"] = f"{type(e).__name__}: {e}"
            if getattr(sketch, "TypeId", "Sketcher::SketchObject") != "Sketcher::SketchObject":
                sketch = None
            if sketch is not None:
                tr["inEdit"] = getattr(sketch, "Name", "?")  # a name: the trace is read as JSON
        subs = sub_names(name, body, args) if sketch is not None else []
        if made and sketch is None:
            self._step(tr, "active", self._active_body, made)
        if name.startswith(PLAN_TOOLS):
            self._step(tr, "plan", self._plan, made)
        if name.startswith("robot_"):
            self._step(tr, "robotFramed", self._robot_frame, doc, args, body, made)
        else:
            self._step(tr, "fit", self._frame, tr, name, made, sketch, subs)
        _last_change_sel[:] = [getattr(o, "Name", "?") for o in made] if sketch is None else []
        _read_sel[0] = False
        if sketch is not None:
            # A sketch in edit with other bodies between it and the camera
            # (sk 029, 037, 053, 060): those made see-through until the next
            # change, as view state; its own body is never touched.
            self._step(tr, "uncovered", uncover, doc, [sketch], [sketch_box(sketch)])
        elif made and how != "worked on" and name.startswith(UNCOVERED):
            self._step(tr, "uncovered", uncover, doc, made)
        self._step(tr, "inspectionsHidden", inspections_after, doc, name, made)
        if name in FEM_RESULT_TOOLS:
            # Only a call that leaves a result: a later fea_ change (fea_parts,
            # fea_clear) put away the colours (scene_clear) and draws none.
            self._step(tr, "femResult", fem_result_shown, doc, body, self.s)
        if name.startswith(("pd_", "feature_")):
            self._step(tr, "profilesHidden", profiles_hidden, named)
        if name == "meshobj_segments" and (self._step(tr, "segments", segments_shown, made)
                                           or self._step(tr, "segmentsDrawn", segments_drawn, doc, args, body)
                                           or body.get("kept")):
            # The segments' colours show only with the mesh not selected
            # (the selection's green covered them: mesh 009).
            _selected[0] += 1
            FreeCADGui.Selection.clearSelection()
        self._step(tr, "modelTab", _model_tab_back)
        self._step(tr, "viewsFollow", views_follow)
        # What was done, said again now that it is done (and naming what it
        # made, with the answer's key value): held until the next changing
        # call (HOLD_MS).
        self._step(tr, "words", say, what if getattr(self, "_own_words", False) else change_words(what, body), HOLD_MS, where)
        if self.mode != "short":
            # At a batch's short pace the next call's pause paints it (and a
            # picture of the window paints before it grabs): no paint here.
            _paint()

    def _new_objects(self, doc):
        """The objects new in doc since before the call (its names then:
        _names_now), shown ones first, at most NEW_MOST."""
        before = getattr(self, "_names0", None)
        if before is None or getattr(self, "_doc0", None) != getattr(doc, "Name", None):
            return []  # another document now (doc_open, doc_new): not this call's results
        objs = list(doc.Objects)
        if len(objs) > NEW_LOOK_MOST:
            return []
        new = [o for o in objs if o.Name not in before]
        shown = [o for o in new if _seen(o)]
        return (shown or new)[:NEW_MOST]

    def _read_shown(self, name, args, body):
        """What a read worked on, selected (its page in front for a TechDraw
        read, its sheet for a spreadsheet read, else the 3D view brought back
        in front of a page: td 049): the object it names (READ_KEYS), the
        faces and edges it names ("Block.Face6": a measure's a and b; a
        shape_query's found faces on its body), not a whole Part Design body,
        and only in the agent's document when it is the one in front. A read
        that names nothing puts back the last change's selection when an
        earlier read had replaced it (asm 050-055: shape_query's
        ConnectingRod stayed for asm_check, asm_fits, asm_bom). The labels."""
        doc = self.s.doc
        if doc is None or FreeCAD.ActiveDocument is None or FreeCAD.ActiveDocument.Name != doc.Name:
            return None
        if name.startswith(tuple(PAGES)):
            ref = (body or {}).get("page") or (args or {}).get("page")
            page = _objects(doc, [ref]) if isinstance(ref, str) else []
            page = page or pages_of(_objects(doc, [(body or {}).get("view"), (args or {}).get("view")]))
            return show_view_of(page[0], read=True) if page else None
        if name.startswith(SHEET_TOOLS):
            sheet = [o for o in _objects(doc, sheet_refs(name, args, body)) if is_sheet(o)]
            if sheet:
                return show_view_of(sheet[0], read=True)
        subs = read_refs(name, args, body)
        own = declared_selection(name, args, body, doc)
        if own:
            objs = [o for o in _objects(doc, own) if not _hidden(o)]
            subs = []
        else:
            objs = [o for o in _objects(doc, [args.get(k) for k in READ_KEYS if args.get(k)])
                    if getattr(o, "TypeId", "") not in ("PartDesign::Body", "Sketcher::SketchObject") or subs]
            # What the read worked on, by its answer (an add-on's SELECTS:
            # a check's body, a preparation's body) — a Part Design body too.
            objs += [o for o in _objects(doc, selects_names(name, body)) if o not in objs]
            objs = [o for o in objs if not _hidden(o)]
        picked = [(o, sub) for o in _objects(doc, [r for r, _s in subs]) for r, sub in subs
                  if r in (o.Name, o.Label) and not _hidden(o)]
        import FreeCADGui

        if not objs and not picked:
            back = _last_change_sel if _read_sel[0] else None
            if back:
                _read_sel[0] = False
                keep = [o for o in _objects(doc, back)]
                if keep:
                    _select(keep)
                    views_follow()
                    return [o.Label for o in keep]
            return None
        front_3d(doc)
        try:
            now = [x.Name for x in FreeCADGui.Selection.getSelection()]
        except Exception:  # noqa: BLE001
            now = None
        if picked:
            _selected[0] += 1
            FreeCADGui.Selection.clearSelection()
            for o, sub in picked:
                _add_sel(o, sub)
            _read_sel[0] = True
            views_follow()
            return [f"{o.Label}.{sub}" for o, sub in picked]
        if now == [o.Name for o in objs]:
            return None
        _select(objs)
        _read_sel[0] = True
        views_follow()
        return [o.Label for o in objs]

    def job_done(self, job):
        """A job's answer shown as its call's would have been (job_listener):
        the read's words with what came of it, and what it read selected.
        "shown" in the trace's "job". Never raises."""
        try:
            srv = getattr(self, "server", None)
            tool = srv.tools.get(job.get("tool")) if srv is not None else None
            if tool is None:
                return None
            args = dict(job.get("args") or {})
            tool = tool.for_call(args)
            ok = job.get("status") == "done"
            body = job.get("result") if ok else {"error": job.get("error")}
            import json

            reply = {"content": [{"type": "text", "text": json.dumps(body if body is not None else {}, default=str)}]}
            if not ok:
                reply["isError"] = True
            self.t0 = job.get("started") or time.time()
            self.after(tool, args, reply)
            tr = getattr(self, "tr", None)
            if isinstance(tr, dict):
                tr["job"] = job.get("job")
            return "shown"
        except Exception as e:  # noqa: BLE001
            _plog(f"Agent Link echo (job {job.get('job')}): {e}\n")
            return None

    def _reopen_sketch(self, gd, args):
        ed = gd.getInEdit()
        sk = getattr(ed, "Object", None) if ed is not None else None
        if sk is None:
            found = _objects(self.s.doc, [args.get("sketch")])
            sk = found[0] if found else None
        if getattr(sk, "TypeId", "") != "Sketcher::SketchObject":
            return None
        if ed is not None:
            if (gd.Document.Name, sk.Name) not in _agent_edits:
                return "left open: not opened by the agent"
            gd.resetEdit()
        return enter_edit(gd, sk)

    def _plan(self, made):
        """A flat plan made (a 2D view, a cut sheet): seen from the top."""
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        v = getattr(gd, "ActiveView", None) if gd is not None else None
        if v is None or not made or gd.getInEdit() is not None:
            return None
        d = v.getViewDirection()
        if abs(d.z) > 0.999:
            return None
        with _Still(v):
            v.viewTop()
        return "top"

    def _open_new_sketch(self, gd, made):
        sk = next((o for o in made if getattr(o, "TypeId", "") == "Sketcher::SketchObject"), None)
        if sk is None:
            return None
        ed = gd.getInEdit()
        if ed is not None and ed.Object is sk:
            return "already open"
        return enter_edit(gd, sk)

    def _frame(self, tr, name, made, sketch, subs):
        """What the call made selected (once: each selection runs the tree's
        and the 3D view's updates), and the view turned and framed on it
        (Mod/AgentLink Follow; the Activity tab's check box): an open
        sketch whole (its own lines' box: sketch_box), else what the call
        made (P5), else the whole document. Nothing that it could select
        and nothing new: the last call's selection is cleared, never left
        standing for this one. Returns how it was framed, or None."""
        import FreeCADGui

        follow = (FreeCAD.ParamGet(PREFS).GetBool("Follow", True) and not name.startswith(tuple(PAGES))
                  and not getattr(self, "_front_other", False))
        animate = fit_animated(getattr(self.s, "batch_now", None), self.mode)
        self._left_sketch = False
        if sketch is not None:
            how = None
            if follow:
                gd = FreeCADGui.ActiveDocument
                v = getattr(gd, "ActiveView", None) if gd is not None else None
                if frame_box(v, sketch_box(sketch)):
                    how = "sketch"
                elif fit_on([sketch], animate):
                    how = "sketch (fit selection)"
            if subs:
                tr["subsSelected"] = _select_subs(sketch, subs)
            elif made:
                _select(made)
            return how
        if not made:
            _selected[0] += 1
            FreeCADGui.Selection.clearSelection()
            if follow:
                from . import around

                with around.part("fit"):
                    return "all" if fit(animate=animate) else None
            return None
        if follow and any(is_bim_container(o) for o in made):
            # A BIM level or building: FreeCAD's Fit selection frames what its
            # view provider draws — the level's label text (bim 020-023), a
            # 65 mm grey fill after bim_reorder (058-066). Framed on what it
            # holds instead (labels, texts, dimensions left out), else on the
            # model with every annotation left out (round 6, item 5). A Draft
            # text or dimension made on its own is still framed on itself.
            _select(made)
            tr["selected"] = [getattr(o, "Name", "?") for o in made]
            gd = FreeCADGui.ActiveDocument
            v = getattr(gd, "ActiveView", None) if gd is not None else None
            box = members_box(made) or model_box(self.s.doc)
            if box is not None and frame_box(v, box):
                return "members" if members_box(made) else "model (annotations left out)"
        shown = framed(made)
        _select(shown or made)
        tr["selected"] = [getattr(o, "Name", "?") for o in made]
        how = None
        if follow:
            from . import around

            self._step(tr, "turned", self._turn, made)
            with around.part("fit"):
                if shown and fit(animate=animate, selection=True) == "selection":
                    how = "made"
                else:
                    how = "all" if fit(animate=animate) else None
        if shown and len(shown) != len(made):
            _select(made)
        return how

    def _active_body(self, made):
        """The body the work went into made active, as a person's
        double-click on it does."""
        import FreeCADGui

        body_obj = next((o for o in made if getattr(o, "TypeId", "") == "PartDesign::Body"), None)
        if body_obj is None:
            body_obj = next((p for o in made for p in (getattr(o, "InList", None) or ()) if getattr(p, "TypeId", "") == "PartDesign::Body"), None)
        gv = FreeCADGui.ActiveDocument.ActiveView if FreeCADGui.ActiveDocument else None
        if body_obj is not None and gv is not None:
            if gv.getActiveObject("pdbody") is not body_obj:
                gv.setActiveObject("pdbody", body_obj)
            return body_obj.Name
        return None

    def _robot_frame(self, doc, args, body, made):
        """A robot framed on itself: the box from its base to its tool point
        (and its tool shape), at least ROBOT_MM across — a robot with no
        drawing of its own (FreeCAD's built-in default has no VRML model)
        gave the whole-document fit a 10 m view of nothing (core 0081-0092).
        The robot selected. "robot" when framed. Never raises."""
        import FreeCADGui

        robots = [o for o in made if getattr(o, "TypeId", "") == "Robot::RobotObject"]
        if not robots:
            robots = [o for o in _objects(doc, [(body or {}).get("robot"), (args or {}).get("robot")])
                      if getattr(o, "TypeId", "") == "Robot::RobotObject"]
        if not robots:
            return self._frame(self.tr, "robot_", made, None, [])
        r = robots[0]
        pts = []
        for attr in ("Base", "Tcp"):
            try:
                p = getattr(r, attr).Base
                pts.append((p.x, p.y, p.z))
            except Exception:  # noqa: BLE001
                continue
        tool = getattr(r, "ToolShape", None)
        b = _box(tool) if tool is not None else None
        if b is not None:
            pts += [(b.XMin, b.YMin, b.ZMin), (b.XMax, b.YMax, b.ZMax)]
        paths = robot_paths(doc)
        pts += [p for line in paths for p in line]
        if not str(getattr(r, "RobotVrmlFile", "") or ""):
            # No model file: FreeCAD draws nothing of the arm (core 0081,
            # 0082, 0092: an empty 7 m view). Its base, tool point and the
            # trajectories marked in the scene only, base to tool point as a
            # line (round 6, item 3).
            marks = [q for q in pts[:2]]
            lines = ([pts[:2]] if len(pts) >= 2 else []) + paths
            self.tr["robotModel"] = "none: no RobotVrmlFile, base and tool point marked"
            self.tr["robotMarks"] = scene_marks(marks, lines)
        _select([r])
        box = grown(box_of(pts), least=ROBOT_MM)
        gd = FreeCADGui.ActiveDocument
        v = getattr(gd, "ActiveView", None) if gd is not None else None
        if box is not None and FreeCAD.ParamGet(PREFS).GetBool("Follow", True) and frame_box(v, box):
            return "robot"
        return None

    def _turn(self, made):
        """A solid made or changed with nothing in edit, and the camera still
        straight along an axis (a sketch's view, or a top view): turned to
        the isometric view at once, as a person turns it to look (a pad
        showed as a flat outline). A person's own tilted view is left."""
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        if gd is None or gd.getInEdit() is not None or not any(_has_solid(o) for o in made):
            return None
        v = gd.ActiveView
        d = v.getViewDirection()
        if max(abs(d.x), abs(d.y), abs(d.z)) <= 0.999:
            return None
        with _Still(v):
            v.viewIsometric()
        d1 = v.getViewDirection()
        return [round(d1.x, 3), round(d1.y, 3), round(d1.z, 3)]


def model_tab_index(titles, current):
    """Of tab titles (a dock area's tab bar, or a QTabWidget's), the index to
    put in front, or None: the Model tab, only when the Tasks tab is the one
    in front (a tab the person chose, such as Agent Link's, is left).
    Plain Python."""
    clean = [str(x or "").replace("&", "").strip() for x in titles]
    if "Model" not in clean or "Tasks" not in clean:
        return None
    if not isinstance(current, int) or not (0 <= current < len(clean)) or clean[current] != "Tasks":
        return None
    return clean.index("Model")


def _model_tab_back():
    """The Model tab in front again when the Tasks tab shows nothing: FreeCAD
    raises Tasks for a task dialog or a sketch and leaves it up, empty (or
    with its helper buttons only), when that ends, with the tree (and what
    was just made in it) behind it. Left alone while a task dialog is open
    or something is in edit in any document (a sketch left open in another
    document stays as it is: A1/S9), and when the person's own tab (any
    other than Tasks) is in front.

    FreeCAD 1.1 docks Model, Tasks (and Agent Link) as tabbed dock widgets:
    their tabs are a QTabBar of the main window, not a QTabWidget, so a
    search for QTabWidget found nothing (P3). Both are looked at here: a
    QTabWidget's own bar is a QTabBar too. Never raises."""
    try:
        import FreeCADGui

        if FreeCADGui.Control.activeDialog() or edit_document() is not None:
            return False
        if FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit() is not None:
            return False
        _QtCore, _QtGui, QtW = _qt()
        mw = FreeCADGui.getMainWindow()
        for bar in mw.findChildren(QtW.QTabBar):
            try:
                i = model_tab_index([bar.tabText(k) for k in range(bar.count())], bar.currentIndex())
            except RuntimeError:
                continue
            if i is None:
                continue
            # FreeCAD's own way first (Gui::ControlSingleton::showModelView:
            # the Model dock shown and raised), then the tab itself.
            try:
                FreeCADGui.Control.showModelView()
            except Exception:  # noqa: BLE001  (an older FreeCAD)
                pass
            try:
                if bar.currentIndex() != i:
                    bar.setCurrentIndex(i)
            except RuntimeError:
                pass
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _tag(session):
    """An extension's text before each call (session.activity_tag), plain."""
    from . import activity

    t = activity.plain(getattr(session, "activity_tag", "") or "")
    return t + " " if t else ""


def wrap(server, session):
    """Show each call the server runs in the window — batches' calls one by one."""
    echo = Echo(session)
    plain = server.call

    def call(params):
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = server.tools.get(name)
        if tool is not None:
            tool = tool.for_call(args)  # a changing tool's read shows as a read
        from . import around

        try:
            with around.part("echoBefore"):
                echo.before(tool, args)
        except Exception as e:  # noqa: BLE001  (the echo never stops a call)
            _plog(f"Agent Link echo (before): {e}\n")
        reply = plain(params)
        try:
            with around.part("echoAfter"):  # its view fit is in "fit" as well
                echo.after(tool, args, reply)
        except Exception as e:  # noqa: BLE001
            _plog(f"Agent Link echo (after): {e}\n")
        return reply

    server.call = call
    server.echo = echo  # a batch's heavy read, run as a job, is shown through it (tools.py _echo_job)
    echo.server = server
    _JOB_ECHO[0] = echo
    try:
        from . import jobs

        jobs.listen(job_listener)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (jobs): {e}\n")
    return echo


# The window's echo a job's end is shown through (wrap()).
_JOB_ECHO = [None]
JOB_RETRY_MS, JOB_RETRIES = 400, 50


def job_listener(job):
    """A job ended (on its own thread): its answer shown in the window — its
    words, what it read selected — as a call's are, when no call gave the
    answer back (jobs.answered: the call that waited, or a batch). Handed to
    the GUI thread (gui_link's poster), then deferred there through
    overlay.later, and shown only while no call is in hand (a call's own
    words go first; tried again a little later). Never raises."""
    try:
        if job.get("answered") or _JOB_ECHO[0] is None or not _on():
            return
        post = _link_poster()
        if post is None:
            return  # no window link to hand it to (a poster made here would live on this thread)

        def on_gui():
            from . import overlay

            overlay.later(0, lambda: _job_shown(job, 0))

        post.post(on_gui)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (a job's end): {e}\n")


def _link_poster():
    """The window link's poster (made on the GUI thread: gui_link), or
    None. Never raises."""
    try:
        import agentlink_state

        link = getattr(agentlink_state, "link", None)
        p = getattr(link, "_poster", None) if link is not None else None
        if p is not None:
            return p
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import gui_link

        return gui_link._POSTER[0]  # one made on the GUI thread before, if any
    except Exception:  # noqa: BLE001
        return None


def _busy():
    """A call is in hand in the window's link (agentlink_state.link.in_call)."""
    try:
        import agentlink_state

        link = getattr(agentlink_state, "link", None)
        return bool(getattr(link, "in_call", False))
    except Exception:  # noqa: BLE001
        return False


def _job_shown(job, tries):
    try:
        if job.get("answered") or job.get("echoed"):
            return
        if _busy():
            if tries < JOB_RETRIES:
                from . import overlay

                overlay.later(JOB_RETRY_MS, lambda: _job_shown(job, tries + 1))
            return
        job["echoed"] = True
        ec = _JOB_ECHO[0]
        if ec is not None:
            ec.job_done(job)
    except Exception as e:  # noqa: BLE001
        _plog(f"Agent Link echo (a job's end): {e}\n")
