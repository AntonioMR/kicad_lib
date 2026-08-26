# Component Library — trial layout

Reusable, general-purpose component library, exposed to KiCad as a database library backed by `lib_db/catalog.sqlite`. Every catalog row is selectable and placeable in a schematic, including ones that don't have a real IPN yet.

## Layout

```
lib/
├── lib_sym/                   # .kicad_sym symbol libraries
├── lib_fp/                    # .pretty footprint libraries
├── lib_packages3d/            # .step / .wrl 3D models
├── lib_db/
│   ├── source/                # CSV per family — SOURCE OF TRUTH, reviewed in PRs
│   ├── build_db.py            # regenerates catalog.sqlite from source/*.csv
│   └── catalog.sqlite         # generated — see "Generated database" below
└── catalog.kicad_dbl          # KiCad Database Library config — see setup below
```

`build_db.py` picks up any `*.csv` dropped into `source/` automatically, one
SQLite table per file — add, split or rename families freely.

### Families

33 families in `source/`, grouped by category (matches the taxonomy this
library was organized against):

| Category | Families |
|---|---|
| Passive | `resistor`, `potentiometer`, `capacitor` (ceramic), `capacitor_tan`, `capacitor_elec`, `capacitor_film`, `inductor`, `ferrite` |
| Semiconductors | `diodes`, `transistor`, `opto` |
| ICs | `ics` (uncategorized catch-all), `microcontroller`, `processor`, `logic`, `regulator` (power management), `analog`, `interface`, `memory`, `audio` |
| Connectors | `connectors` |
| Power & Protection | `relays`, `fuses`, `esd_protection` |
| Sensors & Actuators | `sensors` |
| Displays & Indicators | `leds`, `displays` |
| Mechanisms | `switches`, `encoders`, `drivers`, `mechanical` |
| Test | `testpoints` |
| Other | `crystals` |


## CSV column schema

Every CSV in `source/` shares a common set of columns, plus family-specific
technical columns (e.g. `Resistance`/`Power` for resistors, `Vf`/`Vr` for
diodes). `build_db.py` only requires `IPN`, `Symbol`, `Footprint` to be
present; everything else is carried through as-is. Every `lib_sym/*.kicad_sym`
`_TEMP` symbol mirrors its family's CSV columns 1:1 by name, and
`catalog.kicad_dbl` maps each column straight through to a same-named
field, so all three (CSV, symbol template, DB config) stay in sync by
construction.

Common columns: `IPN, Part Number, Description, Value, Symbol, Footprint,
Manufacturer, Manufacturer Part Number, Manufacturer Alternative, MPN
Alternative, ..., Package, Datasheet, Created By, Created On, Approved By,
Approved On, Revision, Comments`


- **Part Number** — the DB key (see below). A locally unique, human-readable
  identifier, distinct from `Manufacturer Part Number`.
- `Manufacturer Part Number` / `Manufacturer` — the part's manufacturer and
  its part number with that manufacturer.
- **IPN** — internal part number. Marks a component as reviewed and
  authorized for use. Unassigned components carry a `-????` suffix
  placeholder (e.g. `IPN_R-????`) until a real one is issued.
- `Symbol` / `Footprint` — the KiCad symbol and footprint for the part.
- `Approved By` / `Approved On` — production-readiness metadata, unrelated
  to the IPN check.

## IPN — not a gate at selection time

Every row in `lib_db/source/*.csv` is selectable from KiCad, assigned IPN or
not. If a component is used in a design, it should be assigned a unique IPN
value. A finished project's BOM should not contain any components without a
valid IPN value.

The unassigned placeholder is a `-????` suffix (e.g. `IPN_C-????`); any
other suffix (e.g. `IPN_C-0001`) counts as assigned.

## Component review template

Symbols, footprints and 3D models come from a mix of sources — built from
scratch, adapted from a manufacturer library, or pulled from KiCad's
standard libraries — so each one needs a manual review pass before it's
trusted for a real build, regardless of where it came from. A component is reviewed and recorded by direct commit, in two separate steps.

**Step 1 — on first use, before assigning a real IPN.** Work through the
checklist below, then replace the row's `IPN` `-????` placeholder with a
real value and fill in `Created By` / `Created On`. A real IPN means the
symbol/footprint has passed this checklist and is safe to place in a
schematic and build into a prototype.

**Step 2 — once validated on a built prototype or production run.** Fill
in `Approved By` / `Approved On` in a follow-up commit. A finished/
production BOM should not contain parts missing either a real IPN or
`Approved By`/`Approved On`. A prototype BOM only needs the real IPN.

### Checklist

**Symbol**
- [ ] Pin count, numbers and names match the datasheet pinout exactly.
- [ ] Pin electrical type (input/output/bidirectional/power/passive/NC) is set correctly — drives ERC.
- [ ] Power and ground pins are typed `Power input` (or hidden + `Power`) so ERC catches an unconnected rail.
- [ ] Unused/NC pins are marked `NC` and, where the datasheet requires it, actually left unconnected.
- [ ] Revision field populated in symbol file.
- [ ] Fields populated per the family's CSV schema — `Manufacturer Part Number`, `Datasheet` link, `Package` at minimum.
- [ ] Graphical pin layout is legible (grouped by function, no overlapping pins).

**Footprint / land pattern**
- [ ] Pad shapes, pitch and count match the manufacturer's recommended land pattern from the datasheet/package drawing.
- [ ] Where no manufacturer land pattern is given, the footprint follows IPC-7351 (nominal/least/most material condition per the part's density level).
- [ ] Pad numbering matches the symbol's pin numbering 1:1 (verified with an ERC/footprint-association check, not just by eye).
- [ ] Courtyard (`F.CrtYd`) is present and sized per IPC-7351 Level B (Nominal/Median density) courtyard excess. Library default is **0.20 mm** — the industry-practice value, tighter than the literal IPC-7351 Level B range of 0.15–0.25 mm (often cited as 0.25 mm). Courtyards must not overlap adjacent footprints at this spacing.
- [ ] Footprint origin/anchor point is consistent with the family convention (typically pin 1 or body centroid).
- [ ] Silkscreen (`F.SilkS`) shows a pin-1 marker, does not overlap pads, and courtyard/fab layers agree on the body outline.
- [ ] 3D model is assigned, correctly scaled/rotated/offset, and visually matches the datasheet package drawing when previewed in the footprint editor.

**DNP and testpoint conventions**
- [ ] Populate-option parts are marked with KiCad's `Exclude from BOM` / `Do not populate` footprint attribute, not silently omitted from the schematic.
- [ ] Test points use the `testpoints` family and the `TP` reference prefix, not a repurposed connector or via-only footprint.
- [ ] A DNP part still carries a complete, reviewed symbol/footprint pair — DNP affects BOM/assembly output, not review scope.
- [ ] Revision field populated in footprint file.

## Generated database

`lib_db/catalog.sqlite` is **generated from `lib_db/source/*.csv`**, never
edited by hand. Regenerate it with:

```bash
python3 lib/lib_db/build_db.py
```

Whether `catalog.sqlite` itself gets committed (convenience, regenerate-and-
diff-check in CI) or gitignored (regenerate on demand, no generated binary in
the tree) is still an open call — not decided yet, so no pre-commit hook is
wired up for it yet either. The CSVs are tracked either way (`hardware/.gitignore`
carries an explicit `!lib/lib_db/source/*.csv` exception to the repo's
blanket `*.csv` ignore rule).

## KiCad Database Library — setup

`catalog.kicad_dbl` is confirmed working (KiCad 8.0.3, native Linux
install). It needs one thing your system may not have yet: **KiCad's
database library always connects over ODBC**, even for SQLite — the
`"type": "sqlite3"` in the config does not bypass it.

1. Install unixODBC and a SQLite ODBC driver, then confirm it registered:
   ```bash
   sudo apt install unixodbc libsqliteodbc   # Debian/Ubuntu — other distros: unixodbc + a SQLite3 ODBC driver package
   odbcinst -q -d                            # must list a driver named SQLite3
   ```
2. `connection_string` in `catalog.kicad_dbl` has to reference that
   exact driver name and the right path:
   ```
   Driver={SQLite3};Database=${CWD}/lib_db/catalog.sqlite
   ```
   `${CWD}` is the only variable KiCad expands in this string, and it
   resolves to the directory holding `catalog.kicad_dbl` itself
   (`lib/`) — **not** the project directory (`${KIPRJMOD}` is not expanded
   here and will silently fail to connect if used).
3. Restart KiCad after installing the driver so it picks up the new ODBC
   registration.
4. Make sure `lib_db/catalog.sqlite` exists first — see "Generated database"
   above.
