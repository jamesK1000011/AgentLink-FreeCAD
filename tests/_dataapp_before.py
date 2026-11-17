# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the hub's application tools of families/app.py and of
# `addon` (families/unattended.py) now kept as data, at the commit they were
# converted from (tests/test_dataapp_data.py's BASE; OLD_AT for `addon`): name, description,
# inputSchema, changes, reads, group. Written by
#   python3 tests/test_dataapp_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "pref_get": {
  "name": "pref_get",
  "description": "Read FreeCAD's settings (the parameter tree Edit > Preferences writes): path a group (\"BaseApp/Preferences/View\"; BaseApp/Preferences when left out) answers values { name: { type Boolean | Integer | Unsigned | Float | String, value } } and groups (its subgroups, to walk down); name: one setting. Only settings ever changed are stored: one that is absent is at FreeCAD's default (refused as not found, with the names stored). Works headless. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "pref_set": {
  "name": "pref_set",
  "description": "Change FreeCAD's settings: path (the group), then name + value or values { name: value }. The type follows the stored setting's own; for one not stored yet give type (bool, int, uint, float, string) or it is taken from the value — a wrong type is stored beside the right one and FreeCAD ignores it, so check with pref_get. Reply: set { name: { was, now, type } }, appliesAtNextLaunch. Most apply at once; the theme, stylesheet, language and toolbars after app_restart. Refused for the person's own: Agent Link's ExtensionRepos, the switches add-ons guard, the Addon Manager's groups, the macro folder and program paths (…BinaryPath, …Executable).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "value": {},
    "values": {
     "type": "object"
    },
    "type": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "app"
 },
 "pref_reset": {
  "name": "pref_reset",
  "description": "Take settings back to FreeCAD's defaults by removing the stored values: path (the group), names. Reply: reset, notSet (names not stored there: already at the default, or misspelt). Guarded settings are refused as in pref_set.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "names": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "names"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "pref_pack": {
  "name": "pref_pack",
  "description": "Preference packs (themes and their settings; FreeCAD's own, saved ones and add-ons'): with nothing, packs lists their names; apply: name sets every value the pack holds (reply: values, how many). The stylesheet and theme show after app_restart; navigation and colours at once. There is no un-apply: an add-on that keeps a settings history can take it back.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "apply": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "app"
 },
 "cmd_list": {
  "name": "cmd_list",
  "description": "FreeCAD's commands (every toolbar button and menu item is one): name, menu text, tip, shortcut, and refused (why cmd_run will not run it). query: part of a name or words of its menu text or tip; limit (80). Only commands of workbenches already activated in this run exist (workbench { activate } loads one). Reply: commands, count, workbench (the active one). Window only. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "query": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "cmd_run": {
  "name": "cmd_run",
  "description": "Run a FreeCAD command by name (Std_ViewFitAll, Std_ViewIsometric, PartDesign_Pad …) as pressing its button would: on the window's current selection (selection sets it) and the document in front (doc_switch { front: true }), in the active workbench. A command that is not active (greyed out) is refused, since FreeCAD would silently do nothing; commands that open a modal dialog, run macros or quit are refused with the tool for the job. Many modelling commands open a task panel and wait: dialog_answer presses its OK or Cancel. index: the item of a group command (0). Reply: ran, wasActive, workbench, document, objectsAdded — a command gives no result of its own, so read the model after (session_state). The headless tools do modelling better; this is for view and window commands. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "index": {
     "type": "integer"
    }
   },
   "required": [
    "name"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "app"
 },
 "menu_list": {
  "name": "menu_list",
  "description": "The window's menu bar as the person sees it in the active workbench: items [{ path: [titles], command (its name for cmd_run), enabled: false when greyed, checked for toggles }]; menu: one top menu only (all of it; without it, the first limit 400 items). Menus change with the workbench. Window only. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "menu": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "menu_run": {
  "name": "menu_run",
  "description": "Press a menu item by its path of titles ([\"View\", \"Standard views\", \"Fit all\"]; as menu_list gives them, case and a trailing … aside). A greyed item is refused (it would do nothing), a submenu too, and what cmd_run refuses (modal dialogs, macros, quit). Reply: pressed, command, checked (a toggle's state after). Acts on the selection and the document in front, as cmd_run. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "app"
 },
 "workbench": {
  "name": "workbench",
  "description": "The window's workbenches: with nothing, active (its internal name, e.g. PartDesignWorkbench) and workbenches (their menu names); activate: a menu name or internal name (\"Part Design\", \"BIM\", \"FEM\") switches to it, loading it the first time (seconds; its commands and menus exist only from then on). Reply: active, was. Changing tools switch workbench by themselves; this is for cmd_run and menu_run. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "activate": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "show": {
  "name": "show",
  "description": "Show or hide objects in the window as the tree's eye does: objects (names or labels; left out or \"all\": every body and top-level shape), visible (true; false hides). A PartDesign body shown also shows its tip, the finished part. Reply: visible or hidden [labels], unknown (names not found; the rest still done). Hidden parts are left out of view_render and of checks that go by what is shown. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {},
    "visible": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "app"
 },
 "selection": {
  "name": "selection",
  "description": "Set the window's selection for cmd_run and menu_run to act on: objects [names or labels] replaces it with those whole objects (faces and edges are picked with gui_input clicks); no objects clears it; clear: false with no objects reads it instead (detail gives the picked faces and edges). A wrong name is refused and the selection left as it was. Reply: selected [labels], document. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "window_snapshot": {
  "name": "window_snapshot",
  "description": "A picture of the FreeCAD window as the person sees it (toolbars, tree, panels, 3D view), or part: one dock panel by its title (\"Report view\", \"Model\", \"Agent Link\"; a wrong title lists them). Drawn by Qt in the background: no screen recording, the window need not be in front. path: a .png (window.png in the session's folder); inline: false leaves the picture out of the reply. Reply: path, width, height. For how something looks, never as proof a step worked: read state for that. Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "part": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "inline": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "snapshot_latest": {
  "name": "snapshot_latest",
  "description": "The person's newest screenshot (index 2, 3 … for older ones) as a picture with their marks (original: true without), with its note, numbered pins and their comments, workbench and time; a note says when they are still marking it up. Only the person takes them (the camera button, Alt+Shift+S): none yet is refused. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "index": {
     "type": "integer"
    },
    "original": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "snapshot_list": {
  "name": "snapshot_list",
  "description": "The person's screenshots, newest first, without the pictures: time, note, pins, saved path. snapshot_latest { index } shows one. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "app"
 },
 "addon": {
  "name": "addon",
  "description": "FreeCAD's Addon Manager without its dialog (FreeCAD 1.1 and newer; works headless): action list (the folders in the Mod folder, with version; managedBy marks Agent Link's own, updated by agentlink_update, not here) | search { query } (part of a name, in the official catalog, fetched once a day) | install { name, url? (https / git address or a folder; else the catalog), branch?, confirm: \"install <name>\" } | update { name, confirm: \"update <name>\" } (from where it was installed; one copied into the Mod folder by hand has no recorded source, and its first update takes url, which is then recorded) | remove { name, confirm: \"remove <name>\" }. confirm must be typed by the person, word for word: an add-on is code FreeCAD runs. Each install or update is then loaded in a separate headless FreeCAD (a smoke test, a minute or so) and rolled back when that fails. A new add-on's workbench shows in the window only after app_restart. Reply: installed / updated / removed, folder, smoke.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "list",
      "search",
      "install",
      "update",
      "remove"
     ]
    },
    "name": {
     "type": "string"
    },
    "query": {
     "type": "string"
    },
    "url": {
     "type": "string"
    },
    "branch": {
     "type": "string"
    },
    "confirm": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "unattended"
 }
}
''')
