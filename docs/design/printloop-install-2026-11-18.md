# PrintLoop install for the OrcaSlicer server (18 Nov 2026)

## Aim

The OrcaSlicer Agent Link server on the Mac loads PrintLoop with no
environment variable and no manual clone. PrintLoop arrives like the other
add-ons: the hub pins it, and the launcher installs it at agentlink_update.

## How it works

1. `packaging/addons.json` has the key `serverAddons`. Each entry is a
   repository at a pin, as a source is. Its `server` is the stdio name of a
   source (`orcaslicer-agentlink`).
2. PrintLoop's pin is `packaging/pins/printloop-ref`. Bump it as you bump
   the other pins.
3. At an update, the launcher reads the pin. It fetches the files that
   PrintLoop's `FILES` lists into the hidden folder `.server-addons` of the
   new set. The pin is part of the set version. Thus a new pin makes a new
   set and a new publish.
4. `publishStdio` copies PrintLoop into the server's own app folder:
   `~/.config/orcaslicer-agentlink/app-<commit>/addons/PrintLoop-OrcaSlicer`.
   It writes `addons/.id` (the server commit and each add-on commit). It
   writes the same text into `state.json` as `hubPinned`.
5. `orcalink/addons.py` searches the `addons` folder of its own app copy.
   It finds that folder from the module location. Each child folder is a
   repository root that holds a package. `ORCALINK_ADDONS` still works.
6. `orcalink/reload.py` compares `addons/.id` with the value at the start
   of the process. When only the add-ons change, the server starts itself
   again in place at the next call.
7. The OrcaSlicer extension's own launcher fetches a newer commit at a
   start. It copies the `addons` folder of the current app folder into the
   new one. Thus PrintLoop stays when that launcher moves ahead of the pin.

## Security

- The launcher never puts an add-on into FreeCAD's Mod folder, into
  `~/AgentLink`, or into a folder that the agent or the FreeCAD tools write.
  An add-on folder that the agent can write is code execution without the
  person's OK.
- `orcalink/addons.py` never searches the user's writable folders by
  default. A test makes sure that a folder under `~/AgentLink` is not
  searched.

## Who approves an install (decision 3 of 18 Nov)

- Every add-on install goes through `approve_code`.
- Exception: the hub's own pinned add-ons. These are the project's own repositories (owner jamesK1000011)
  in `addons.json`. agentlink_update installs them with no OK for each
  install. The pin bump in the hub is the OK. PrintLoop is one of these.
- A third-party add-on does not go into `addons.json`. It goes through
  `approve_code` (agent "perms" builds it). Do not add a third-party
  repository to `serverAddons`.

## Limits

- The bundled extension (`build.sh`) does not include server add-ons.
  PrintLoop arrives at the first agentlink_update.
- The bake-off does not test PrintLoop in FreeCAD. PrintLoop's own CI tests
  it.
