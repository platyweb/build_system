# Handoff: templatising the EMS build system for any building

**State as of 2026-10-21:** phases 0–6 and 8 are done. Phase 7's project CSS
and fonts are in; a few assets are still owed (see [Open items](#open-items)).
**St Peters is gone from the working tree** (owner's decision, 2026-10-21; the
committed history keeps it). `site/` now holds **site1**, a site-neutral name
for the building whose meters export the owner dropped in
(`site/data/meters.csv`, the same file as `examples/6hl/meters.csv`). Its
data is only what that CSV gives (see [site1](#site1)).
**`README.md` is the engine reference.** It covers every site file, the
modules, how-tos, `--check`, regression and the upgrade workflow. This
handoff keeps the history and the open items.
The owner commits by hand; everything since their last commit is uncommitted.
Last verified state (2026-10-24):
- `python _build/regress.py check`: every golden identical (site1 and three
  examples); re-baselines 7 and 10–26 are accepted;
- `pytest`: all pass. `test_engine_neutral` names the owner's four
  old-layout examples as its one exception (`KNOWN_CLIENT_LINES`);
- `build.py --check`: site1 passes with 4 warnings: its missing floorplans
  and the dummy tenants' three missing Docs PDFs. The examples pass with
  none.

---

## 1. What this is and where it's going

`build_system` generates an Optergy EMS dashboard: static `.htm` pages, plus
generated blocks in the runtime JS. It started as a one-building tool for
**St Peters**, a 47-floor office tower ported from the Leadenhall site, with
that building hardcoded into the engine.

The goal is a **starter template, forked once per building**, that handles any
building:
- any floor count or naming;
- optional modules;
- any utility mix;
- multi-building campuses.

**St Peters was the reference site** until 2026-10-21. Its generated output
stayed byte-identical through every phase, except for explicitly approved
re-baselines. `site/` is now site1, under the same rule.

### Decisions made with the owner (don't relitigate)
| Topic | Decision |
|---|---|
| Repo model | Starter template, one repo per site; the template is split off as a fresh repo in Phase 7. `site/` holds the building being built: St Peters until 2026-10-21, now site1 |
| Meter source of truth | site1: `site/data/meters.csv`, the export read as it is (owner, 2026-10-21). A site may instead keep `meters.yaml` (level → core → meter, 2026-10-20), which `_build/import_meters.py` makes from an export; never both |
| Data file names | Numbered in fill-in order (`00_site.yaml`, `01_pages.yaml` … `16_sidebar.yaml`, `build.DATA_FILES`; `site.yaml` moved into `data/` and frozen pages put first, both at the owner's request); the build finds a file with or without its number. Unnumbered names, root `site.yaml`, `meters.csv` and `tenants.yaml` still work for older sites |
| Data flow | Site data files → build → JS. The build never reads data back out of JS |
| Regression bar | The site's output byte-identical every phase (St Peters until 2026-10-21). Re-baselines only when pre-approved, each the only change in its step, logged in `site/golden/CHANGELOG` |
| St Peters' frozen pages | Removed (2026-10-21, at the owner's request), before St Peters itself. Switchboards, risers and the home page are generated from data; the one-off pages (landlords, landlord/tenant split, CHW/LPHW systems, tariffs, switchboard overview, building performance calculation, report template, meter docs) were dropped with their sidebar links. The `pages` module stays in the engine for other sites |
| Pages and menu | `data/01_pages.yaml` lists every page the site builds, laid out as its sidebar menu (2026-10-21, owner). The build makes only what it lists, derives the modules from it and generates the sidebar from it, so `sidebar.yaml` and `site.yaml modules:` are for older sites only. A listed page no module builds is the site's own: `site/templates/<key>.html.j2`, else `pages/` fragments, else an empty page (header, menu, scripts) |
| Tenant catalog | Its own file, `tenants.yaml` `tenants:` (owner, 2026-10-21), keyed by short name; each level's `cores:` stays in `floors.yaml` |
| Bootstrap | The full Bootstrap 5.3 CSS stays for good, and markup prefers its classes over project CSS (owner, 2026-10-21). Its JS and source maps are gone (re-baseline 14). The project CSS also relies on its `--bs-*` colours, `data-bs-theme` dark mode and Reboot |
| Campus layout | One subfolder per building (`<slug>/<building>/…`). Single-building sites keep flat filenames |
| Git | **No commits by the assistant.** The owner reviews and commits manually |

---

## 2. Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # jinja2, pyyaml, pytest

.venv/bin/python _build/build.py                           # full build of site/ → project/site1/
.venv/bin/python _build/build.py floor_ground              # rebuild one page into the existing output
.venv/bin/python _build/build.py --check                   # validate site data + a trial build (temp dir); writes nothing
.venv/bin/python _build/build.py --site examples/campus --out /tmp/out   # build another site elsewhere
.venv/bin/python _build/build.py --modules switchboards    # override site.yaml modules for one run

.venv/bin/python _build/regress.py check                   # every site's fresh build vs its golden
.venv/bin/python _build/regress.py diff --against HEAD     # what the uncommitted engine change does to every site
.venv/bin/python -m pytest -q tests/                       # unit tests + the golden check
git config core.hooksPath .githooks                        # once per clone: the pre-commit hook runs the golden check
```

Notes:
- **Node is used** for `node --check` on the generated JS; it's skipped if absent.
- **`project/` is fully regenerated** on every full build. The build only wipes
  a directory it created (`project/.build-output` marker).

---

## 3. Repo layout

```
_build/build.py              engine: staging, layout derivation, builders, the menu, MODULES, --check, CLI
_build/site_data.py          the configured site: configure() and its paths/settings, every data reader,
                             page_location()/relative_url(), render_page(). Imported by build.py and the module files
_build/jsblocks.py           renders/injects generated JS blocks (METER_REGISTRY, POINTS, BACNET_CONFIG, REPORT_URLS,
                             REPORT_CARDS, SIDEBAR_HTML, SIDEBAR_RUNTIME, OVERRIDE_FILE)
_build/linkcheck.py          --check's output checks: data-point/meter ids on built pages; referenced-but-missing files
_build/meters_yaml.py        meters.yaml reader + writer (level → core → meter; rows identical to the CSV reader's)
_build/import_meters.py      meters.csv export → the site's meters YAML, checked by reading it back
_build/generate_meter_registry.py   meters.csv reader + normalisers (name is historical: it no longer generates anything itself)
_build/build_switchboards.py, build_risers.py   the `switchboards` / `risers` modules (run(env, only))
_build/regress.py            golden regression harness (multi-site); `diff --against REF` builds with an older engine
_build/migrate_js_data.py    ONE-OFF (Phase 2): JS → YAML migration. Never committed. Delete after committing Phase 2
_templates/                  engine templates + partials/macros.j2
_assets/                     engine runtime skeleton (project JS, vendor libs, generic images). Copied into every build.
                             Site-neutral: its generated blocks are empty (the build fills the staged copy)
site/                        site1 — everything specific to the building being built
  data/                      00_site (identity, bacnet, utilities, floor_page), 01_pages (the menu), 02_floors (levels),
                             04_points (the incomer page), meters.csv (the export, read as it is)
  golden/                    regression manifest + CHANGELOG
examples/minimal/            "Acme Depot": single storey, electricity/solar/gas/water, building performance, no tenants (+ golden).
                             Numbered data files + meters.yaml: what a new site starts from
                             (examples/campus keeps the older root site.yaml, unnumbered names and meters.csv, proving they still build)
examples/campus/             "Riverside Campus": 2 buildings, subfolders, switchboards with cross-building bus tie,
                             a riser split over two pages (+ golden)
examples/tower/              "Northgate House": 4 storeys, two tenants with their own pages, an SVG schematic (+ golden)
                             (all three have placeholder floorplans in assets/img/floors/)
tests/                       test_golden (wraps regress check), test_jsblocks, test_levels, test_site_config, test_campus,
                             test_check (--check), test_tenants, test_meters_yaml, test_engine_neutral (no client data in engine/examples),
                             test_template_coverage (every template rendered by an example), test_engine_conventions
                             (data_path, render_page, template URLs, no module imports build), test_regress, …
.githooks/pre-commit         regress.py check + test_engine_neutral before each commit (git config core.hooksPath .githooks)
_baseline/                   (gitignored, ~45 MB) full copy of each last golden build. Used only to print readable diffs
```

---

## 4. How a site is described (cheat sheet)

**`site.yaml`.** The full examples are `site/data/00_site.yaml` (office tower),
`examples/minimal/data/00_site.yaml` and `examples/campus/site.yaml` (an older
site's root location, kept as the backward-compatibility proof).

| Key | Meaning |
|---|---|
| `slug` | Output dir `project/<slug>/` |
| `name`, `short_name`, `ems_name`, `postcode`, `net_internal_area` | Identity (`building.*` in templates) |
| `modules` | Page families to build: `floors incomers home meters_hierarchy schematics building_performance pages tenants energy_flow dials switchboards risers sidebar` |
| `buildings` | Campus only: `[{key, name}]`. More than one → per-building folders |
| `utilities` | `{code: {label, kind: electric\|thermal\|other}}`. The code is the CSS class `.meter-<code>` |
| `bacnet` | `{device, power_offset: {<meter type>: <offset>}}`. Address = `<device>\|<objtype>\|<instance>\|85\|-1` |
| `optergy_lib_version`, `brand`, `footer` | Controller lib cache-bust, sidebar header/footer |
| `optergy_override_display` | Optional. The Optergy display file that live-points.js point overrides post to (`OVERRIDE_FILE`). Blank if unset |
| `summary_roles` | Summary-card catalog `{role: {title, format}}`. Live point from `points.yaml floors:` by (level, role) |
| `floor_page` | `tabs` (`[{id, label, slot, roles}]`), `summary_cards` (`total`/`tenants`/`landlords` → a meter's `function`), `centre_zone`, `zone_suffix`, `zone_subtitles`, `report_titles`, `summary_label`, `riser_card_link` |
| `tenant_page` | `summary_label`, `tabs` (subset of floor_page tab ids) |

**`data/floors.yaml` is the level roster:**
- One `floor_<key>:` entry per level, **bottom → top**; file order is the
  physical order.
- Optional fields: `label`, `nav_label`, `heading`, `page: false`, `building`, `cores`.
- The one other top-level key, `tenants:`, is the tenant catalog.
- Any other field is page data (e.g. `floorplan_tab`).
- Every floor named anywhere else must be a level here; `--check` enforces it.

**`data/meters.yaml`**: `columns: {<core>: <column>}`, then `floor_<key>:` → `floor:` (outside the cores) and
`<core>:` lists of meters, then `unplaced:`. A meter inherits its core's tenant, its core's column and
the next position; the file only states exceptions. Reads into the same rows as the CSV.

**`data/meters.csv`** (the import format, and older sites) columns:
`id,tag,base,type,daily,monthly,parent_id,floor,column,zone,position,function,utility,tenant,tenant_display,main_display`.
- `floor` may list several levels, separated by `/`.
- `utility` may be a code or a label in any case, or "Fluid energy". Fluid
  energy resolves to the thermal code named in `function`.
- Integer cells are validated.

**Starting a new building:** clone the template, `cp -r examples/minimal site`,
edit, build, then run `regress.py snapshot --site site`.

---

## 5. What each phase changed

| Phase | Result |
|---|---|
| 0 | `.gitignore` fix (`/project/`: the old pattern also hid `_assets/css/project/`), `requirements.txt`, `_build/regress.py`, first goldens |
| 1 | All St Peters content moved to `site/`. `configure()` replaces import-time globals. `stage_output()` builds the output from `_assets/` + `site/assets/`. `StrictUndefined`. Site template overrides (`site/templates/`). Optergy version, footer and riser link moved out of engine templates |
| 2 | BMS bindings, points, reports and report URLs moved to `site/data/*.yaml`. `read_meters()` reads meters.csv. `jsblocks.py` generates the JS (JSON-escaped, which fixes the old todo.md n/a bug). One BACnet rule (`bacnet_address`/`demand_address`) + generated `BACNET_CONFIG` read by the runtime |
| 3 | `MODULES` registry + `site.yaml modules:` + `--modules`. Two modules writing one file is an error. Switchboards/risers became modules (no `.generated` suffix). One-shot scripts deleted (they remain in git history) |
| 4 | `floors.yaml` became the ordered level roster (any naming). Ordinal sort/label code removed. `--check` requires every floor key to be a level. `examples/minimal`. regress.py made multi-site |
| 5 | Heat-panel normalisation (re-baseline 3). `utilities:` catalog. Config-driven floor/tenant tabs, summary cards (each optional), centre zone, suffixes. `report_tab_panel` macro. Minimal example gained a Solar PV tab |
| 6 | Campus support: `buildings:`, level `building:`, per-building folders, `relative_url`/`site_href`, a per-folder `sidebar-template.js`, `auto: buildings` + `building:` filters, `nav_label` on incomers/boards, duplicate-key check on floors.yaml. `examples/campus` |
| Extras (2026-10-03) | Site-specific one-offs without template overrides: `_components/` catalog (`image`, `html`, `live_value`), `site/components/` for a site's own, `data/extras.yaml` placements into slots on the floor/incomer/home pages (`components.SLOTS`; empty slots render nothing). `--check` validates placements and warns when one never renders. Backward compatibility: `_components/published.yaml` + `tests/test_components.py`, with `aliases`/`retired` for renamed and removed options. St Peters byte-identical; examples use every component |
| Tenants (2026-10-19) | `site/data/tenants.yaml` merged into `floors.yaml`: a top-level `tenants:` catalog keyed by short name (the `meters.csv` spelling, was `registry_tenant`) with `name` (proper name, was `display_name`) and `slug` (output folder, only where the default from the short name differs). Each level has `cores: {<core>: <short name>}`, derived for St Peters from the meters' North/West/East zones. `read_tenants()` also reads an older site's `tenants.yaml`, with identical output (`tests/test_tenants.py`). `--check` holds cores against the catalog and the meters' tenant tags. Cores aren't rendered yet. Every golden identical |
| Meters YAML (2026-10-20) | Data files numbered in fill-in order, `site.yaml` moved in as `00_site.yaml` (`build.site_file()`; a root `site.yaml` still works), `01_pages.yaml` next (`build.DATA_FILES`, `data_path()`; `--check` warns about a file it doesn't read). Meters moved from `meters.csv` to `03_meters.yaml` (level → core → meter), read by `meters_yaml.py` into the same rows, ordered by id; tenants inherited from cores, so 31 of St Peters' 652 meters state one. `_build/import_meters.py` imports a CSV export. St Peters and campus goldens identical; minimal converted too (re-baselined: only `METER_REGISTRY` row order, meter 8 before 9) |
| Frozen pages removed (2026-10-21) | Owner's request. St Peters' 18 frozen pages and `site/pages/` are gone, and so are `01_pages.yaml`, the empty `11_schematics.yaml` and the 14 hand-drawn LV/riser SVGs only those pages used. Modules now: `floors incomers home meters_hierarchy building_performance switchboards risers sidebar`. Switchboards: `swb_lv01`–`08` from `09_switchboards.yaml` (the sidebar already listed all eight). Risers: the 8 "Rising BusBar" meters (22, 41–44, 80, 90, 93) tagged `function: Riser-meter` in `03_meters.yaml`, giving 12 riser pages; new sidebar `auto: risers` (`build_risers.sidebar_items`). Heat risers have no riser meter in the data, so there's no heat riser page. Home: `07_home.yaml`, the frozen home's tiles, text and report cards as they were. Re-baseline 8 |
| Pages menu (2026-10-21) | Owner's request. A menu-shaped `pages.yaml` (`sections`, `top_items`, `bottom_items`, `unlisted`, `brand`, `footer`) lists every page: `page: <key>` (a generated page, or the site's own: its site template, `pages/` fragments, or an empty page) and `pages: <family>` (floors, incomers, switchboards, risers, tenants, buildings). `build.read_menu()` turns it into the sidebar's items, the modules to run and the own pages; `sidebar_cfg()` / `own_pages()` read either shape. St Peters and minimal converted, `16_sidebar.yaml` and `modules:` removed; the menu data is identical to the old `sidebar.yaml`, and minimal's output is unchanged. St Peters now builds its tenant pages (`pages: tenants`): re-baseline 9. Campus keeps `sidebar.yaml` + `modules:` + its frozen-page list as the backward-compatibility proof |
| BMS points merged (2026-10-21) | Owner's request. `points.yaml` groups every BMS point by page: `named` (was `points:`), `floors` (was `bms_bindings.yaml` rows, now `floor_<key>: {<role>: {id, bacnet}}`), `incomers` (was `incomers.yaml`) and `home` (was `home.yaml`). `build.point_section()` reads either layout; `read_incomers()` / `read_home()` replace direct file reads. St Peters and minimal merged with their comments kept; both read back to the same data and build byte-identical output. Campus keeps the separate files |
| site1 (2026-10-21) | Owner's request: `site/` made site-neutral. St Peters deleted from the working tree; `site/` rebuilt from a copy of `examples/minimal` with only what the owner's meters export gives: levels from its floors, the electricity utility, an incomer page from meters 389/363/362, the menu (floors, incomers, hierarchy). It reads `data/meters.csv` directly. Engine: `meters_hierarchy.yaml` optional (default texts; roots = meters marked `parent: 0`, and those with no parent that feed others); `tenants.yaml` is the tenant catalog's own file; a meter outside the cores keeps its `position` in `meters.yaml`. First golden recorded |
| Floor layout (2026-10-22) | `site.yaml floor_page` gains `floorplan` (`right`, `top` or `none`), `meter_columns` (`1`–`4` or `auto`) and `summary_layout` (`split` or `row`); a level in `floors.yaml` can set any of them for its own pages, tenant pages included. The defaults render every page as before. `--check` warns when a page's cards use more columns than its grid has. `tests/test_floor_layout.py`. The new layouts' CSS is re-baseline 23 |
| Section 6 fixes (2026-10-23) | Owner's request: a guard for each of the "Things that will bite you". `.githooks/pre-commit` (golden check + `test_engine_neutral`); `regress.py diff --against REF` (old engine vs new) and a stale-`_baseline/` guard on `check`'s diffs; examples render every template but dials/energy flow (`test_template_coverage`): campus gained a two-page riser, the new `examples/tower` has tenants and a schematic; `test_engine_conventions` (data paths, `render_page`, template URLs, imports); `render_page()` checks page fields against template globals and defaults `path_prefix`; `site_data.py` split out of `build.py`, so the module files no longer import `build`; the two guarded skeleton lines became generated blocks (re-baseline 24) |
| Tenant docs (2026-10-23) | Owner's request. `tenants.yaml` gains an optional `docs:` per tenant, the menu's Docs link (`site_data.tenant_docs_href`): a file the site ships in `assets/` (linked up to the site folder), a URL or `/docs/…` path as written, or `false` for no Docs item. Unset keeps the old `docs/<slug>-submetering.pdf`, so site1, minimal and campus are unchanged. Tower uses both forms (its golden re-accepted), so `test_check` no longer excuses Docs warnings |
| 7 (part 1) | `_assets/` site-neutral: empty generated blocks; `OVERRIDE_FILE` blank, set from site.yaml `optergy_override_display` (St Peters sets its old `tlb` path); a neutral default `img/sidebar-bg.png`. Engine `building_performance.html.j2` uses `data-point` names and loads meter-templates.js. `--check` adds a trial build in a temp dir (`build_site()` shared with `main()`) and `linkcheck.py` checks on it: an unknown data-point/meter id on a rendered page is an error, a missing file is a warning. This replaced the template scan, which held overridden and unrendered templates to the site's data. Client names reworded out of engine and example comments. Examples: placeholder floorplans; minimal gained `building_performance` |

### Approved re-baselines (all in `site/golden/CHANGELOG`)
1. **Phase 2:**
   - removed the `BMS_BINDINGS`/`REPORT_REGISTRY` blocks from the shipped JS
     (no runtime readers);
   - `ReportUrls` is now generated from `reports.yaml`.

   Verified: Node found the meter, point and URL data identical.
2. **Phase 2 (1b):** the runtime reads `BACNET_CONFIG`. Verified: all 3,260
   meter addresses identical in Node.
3. **Phase 3:**
   - the extended variant `all` became `extra` (every module except `pages`,
     which would collide with switchboards);
   - switchboard output dropped its `.generated` suffix.
4. **Phase 5.0:** heat tab panel attribute wrapping, and its comment now reads
   "Heating Energy Report Tab Content". Identical once comments are stripped
   and whitespace collapsed.
5. **Phase 7, approved 2026-10-03:** comment-only edits in the skeleton JS.
   - `meter-templates.js`: generic placement-field examples (no client tenant
     names); the POINTS schema now reads `<device>|<object type>|<instance>`.
   - `sidebar-template.js`: its header says the block is generated from `sidebar.yaml`.
   - `live-points.js`: the `OVERRIDE_FILE` comment names `optergy_override_display`.

   Verified: every changed file is identical once comments are stripped and
   whitespace collapsed, every raw diff line is a comment, and no `.htm` changed.
6. **Phase 7, approved 2026-10-03:** `floor-tabs.js` lost its zone-header
   colouring handler, which matched on `lphw`/`CHW`/`Electricity`. It was dead
   code: on all 149 pages that load it, no subheader is in the HTML, and
   `floor-tabs.js` loads before `meter-templates.js`. meter-templates.js
   creates the subheaders afterwards (`data-floor-meter`), each with a
   `meter-<utility>` class from the meter's utility code, so colouring was
   already data-driven. `switchTab()` is byte-identical.

7. **Phase 7 assets, approved and accepted 2026-10-21 for both examples:**
   the owner committed the project CSS (10 files) and fonts (31) to
   `_assets/`. Every golden, St Peters and both examples, differed only by
   those 41 added files, each copied verbatim from `_assets/`. Accepted with
   a copy of the engine from before re-baseline 12, so the step held only them.
8. **Frozen pages removed (2026-10-21), owner-requested; dropped with St
   Peters before it was accepted.** Verified step by step against fresh builds:
   - one-off pages: exactly 12 `.htm` removed; `sidebar-template.js` only
     loses their links;
   - switchboards: `swb_lv01`/`02` replaced and `swb_lv03`–`08` + 8 SVGs added
     in the site build, each byte-identical to the extra golden's copy;
   - risers: 3 frozen riser pages removed, 12 riser pages + SVGs added (both
     variants); `meter-templates.js` is identical once the 8 risers' function
     reads `SWB-meter` again; the sidebar swaps the 3 frozen links for 8 risers;
   - home: only `home.htm` changes (content identical; container class, the
     info bar's inline grid style and the bottom cards' 2-column grid wrapper
     differ, and a duplicate `reports.js` tag is gone); the extra build gains it;
   - `pages` module off, `01_pages.yaml` and `11_schematics.yaml` removed: no change;
   - 14 unused LV/riser SVGs removed from `site/assets/`: only those files removed.
9. **Tenant pages built (2026-10-21), owner-requested; dropped with St Peters
   before it was accepted.** With `01_pages.yaml` deciding what's built, the menu's tenants
   entry builds them. Verified: the converted site's menu data equals the old
   `sidebar.yaml`; the site build only adds 73 files under `tenants/` (19
   tenants), each identical to the extra golden's copy; the extra build is
   unchanged.

St Peters' goldens went with it. site1's first golden (2026-10-21) already
includes the CSS and fonts, so re-baseline 7 is now the two examples' only.

10. **site1's floor reports, approved and accepted 2026-10-21.**
    `data/14_reports.yaml` is back, rebuilt for site1 from St Peters' file: its
    header, and the chart settings most of its floors shared, each chart now
    plotting the level's total meter. Verified
    against a build without the file: each of the 6 floor pages only gains its
    two report cards (30 lines added, none removed), `reports.js` only gains
    the 12 URLs in its REPORT_URLS block, and nothing else changes.
11. **site1's dummy tenants, approved and accepted 2026-10-21.**
    `05_tenants.yaml` holds three placeholder tenants (A: ground and 2nd; B:
    3rd; C: 4th and 5th), whose floors come from `extra_floors` because the
    export tags no meter with a tenant; `01_pages.yaml` gains a Tenants entry.
    Verified: 11 files added under `tenants/`, `sidebar-template.js` only
    gains the Tenants sub-menu (27 lines added, none removed), nothing else.
12. **One-line report cards, owner-requested for every site, approved and
    accepted 2026-10-21.** The release note for it: the
    `report_card` macro (floor tabs, tenant pages, incomer pages' plain cards)
    now writes `<div data-report="<image_ref>"></div>`, and `reports.js`
    builds the card on load from a new generated block, `REPORT_CARDS` (each
    report's title, alt text and library id, from `reports.yaml`). Tenant
    floor pages' cards now show the floor page's title (Demand, Consumption).
    The headed and titled cards (home, a `kind: headed` incomer card,
    building performance) are unchanged. A site that overrides
    `partials/macros.j2` keeps its full markup, which still works. Verified,
    old engine vs new on all three sites:
    - only the pages with report cards and `reports.js` change;
    - every changed floor page (site1's 6, minimal `floor_L00`, campus
      `north/floor_n-l01`) renders an identical DOM in headless Chromium once
      its scripts have run;
    - site1's 5 tenant floor pages render identically except that each card
      gains its title band;
    - each `reports.js` differs only by the new skeleton code and its
      `REPORT_CARDS` entries (12, 6, 1); `REPORT_URLS` is unchanged.
    The examples were accepted after re-baseline 7, as a separate step.
13. **The rest of the report cards one line, owner-requested, approved and
    accepted 2026-10-21.** The release note for it: the
    headed cards (home, a `kind: headed` incomer card) and the titled ones
    (building performance) are `<div data-report="<name>"></div>` too, and
    `reports.js` builds all three styles from REPORT_CARDS' new `kind` and
    `subtitle` fields. `kind` defaults by page (home `headed`, building
    performance `titled`, the rest plain), and a placement's `kind`
    overrides it. `report_card_headed` and `report_card_titled` stay in
    `macros.j2` as aliases of `report_card` for site templates that import
    them. The engine templates write no card markup any more. Verified,
    old engine vs new on all three sites:
    - only minimal's `home.htm` and `building_performance.htm` and every
      site's `reports.js` change;
    - both pages render an identical DOM in headless Chromium once their
      scripts have run, and so do the pages with plain cards (minimal
      `floor_L00`, campus `north/floor_n-l01`, site1's floor and tenant floor
      pages) on the new `reports.js`;
    - `reports.js` changes only in its skeleton code and, in minimal, the
      three home and building performance REPORT_CARDS entries gaining
      `kind`/`subtitle`.
14. **Bootstrap JS and the source maps removed, owner-requested, approved
    and accepted 2026-10-21.** The release
    note for it: no page used Bootstrap's JS (no `data-bs-toggle` or
    `bootstrap.*` call anywhere; `data-bs-theme` is CSS only), so
    `base.html.j2` no longer loads `js/bootstrap/5.3.1/bootstrap.bundle.min.js`,
    and `_assets/` drops it, its `.map` and `bootstrap.min.css.map` (about
    1 MB per site, 922 KB of it maps). The Bootstrap CSS stays: the project
    CSS needs its `--bs-*` colours, its `data-bs-theme` dark mode and its
    Reboot (`box-sizing`, line height, margins). Note that both files are
    Bootstrap 5.3.8, in a folder named 5.3.1. Verified, old engine vs new on
    all three sites:
    - each build loses only those 3 files;
    - every page (16 + 7 + 14) changes only by losing that one script line;
    - all 37 pages render an identical DOM in headless Chromium once their
      scripts have run (old DOM minus the script tag).
15. **style.css pruned, owner-requested (CSS plan step 2), approved and
    accepted 2026-10-21.** `style.css` goes from 89,323
    to 60,741 bytes. Removed: selectors no template, component, project
    script, build module or site data can produce (16.9 KB, plus 6.2 KB of
    `@media` blocks left empty; among them the sidebar template's unused
    breakpoint and RTL variants, the theme-toggle pill, floor-card-group,
    the image-overlay system and St Peters' fixed-page grids), commented-out
    code (3 KB), declarations a later rule with the identical selector always
    replaces (0.9 KB), the remixicon icon font (its `@font-face` and the 4
    font files it loaded; the 5th, its `.svg`, never existed) and unused
    `@keyframes`. `tests/test_css_used.py` now fails on a selector no engine
    source can match (it finds 254 in the old file). Verified, old engine vs
    new on all three sites:
    - each build changes only `style.css` and loses the 4 font files;
    - `_build/stylediff.py` (new): every element's computed style, its
      ::before/::after and its box are identical on all 37 pages at 480,
      1024 and 1920 px, light and dark (222 renders). Hover and focus can't
      be rendered, but every removal holds for them too: a dead class can't
      match, and an overridden declaration loses to an identical selector.
    Left for a visible-fix step: the `.switchboard-card-no-animation ::before`
    stray space, `var(---color-primary-dark)`, the `1o5px` padding and the
    font.css URL.
16. **Duplicate stylesheets dropped, owner-requested (CSS plan step 3),
    approved and accepted 2026-10-21.** `diagrams.css` and
    `switchboard.css` repeated `style.css`: every rule of theirs that can
    match is in `style.css` with the same final values. The switchboard,
    riser and schematic templates no longer link them, and they're deleted,
    with `swb.css`, which nothing linked or could match. `meters-hierarchy.css`
    loses 1 KB of dead selectors. `tests/test_css_used.py` now covers every
    linked stylesheet, and fails on a stylesheet no template links (except
    `font.css`, imported, and `tenant-accordion.css`, which goes with the
    unloaded `tenant-accordion.js`). A site template that still links the
    two files gets a `--check` warning and the same look. Verified, old
    engine vs new on all three sites:
    - each build loses the 3 files, and `meters-hierarchy.css` changes;
    - the only page change: campus's 2 switchboard pages lose the two links;
    - `stylediff.py`: identical on all 37 pages, 3 widths, light and dark.
17. **style.css deduplicated, owner-requested (CSS plan step 4), approved
    and accepted 2026-10-22.** 60,741 → 57,944 bytes:
    - 10 selectors that were split over two rules are one rule each (`:root`,
      `.layout`, `.layout .header/.footer/.content`, `.sidebar` twice, `body`,
      `.text-box-content`, `.performance-circle`, `.floorplan-placeholder`);
    - 7 rules with identical declarations share one selector list (the
      title, subtitle and column rules among them);
    - 20 literal colours, gradients and shadows are the palette variables
      that no theme redefines (`--color-primary`, `--gradient-primary`,
      `--shadow-primary`, …);
    - the `--floor-card-group-*` variables (their rules went in
      re-baseline 15) are gone. Every `--color-*`, `--shadow-*` and
      `--gradient-*` stays, even unused here: a site's own pages may use them.

    A declaration moved only when no rule in between could style the same
    element at the same specificity and importance with an overlapping
    property, judged from the class sets 173 rendered pages carry
    (`.layout.has-sidebar` stays split: `.layout.fixed-sidebar` sets
    `height` in between). The card shell, header strip and hover bar weren't
    merged: they differ in more than one value, and the flex patterns that
    repeat most belong to Bootstrap's utilities. Verified, old engine vs new:
    - only `style.css` changes on each site;
    - `stylediff.py` finds nothing on all three sites (222 renders) and on
      44 pages of the St Peters site in git `HEAD`, with its rising busbars
      marked `Riser-meter` so the riser pages render (12 risers, 8
      switchboards, dials, energy flow, building performance, incomers,
      tenant and floor pages; 264 renders). No page renders a schematic.

    `stylediff.py` now skips elements that draw nothing (`script`, …): a page
    script may add one late, and it showed as a count mismatch.
18. **Visible CSS fixes, owner-requested, approved and accepted
    2026-10-22.** The owner chose blue overlays, green solar
    meters, and narrow-screen sizes left as they are. In order:
    - **Stray spaces:** `.switchboard-card-no-animation .primary` is now
      `….primary`, so the card itself gets `grid-column: span 2`. The
      `.switchboard-card-no-animation ::before` rule is deleted: it gave
      every element inside the card an invisible `::before` scaled to zero
      width. The "no animation" card has no hover bar of its own.
    - **Overlays:** `.data-overlay` has `color: var(--color-primary-dark)`,
      not `---color-…`. Switchboard and riser boxes keep their own colour
      (`switchboard-widget.css`); schematic value overlays turn blue.
    - **Invalid padding:** `padding: 5px 1o5px` on `.layout .content` is
      deleted. Browsers always ignored it, so nothing changes.
    - **font.css:** its Devanagari weight-100 URL no longer climbs out of the
      output root. That clears `test_campus` and `test_check`, and
      `test_check` drops its `css/project/` exemption.
    - **Solar:** `.meter-solar` is green, with `--meter-solar-fill` and
      `--hier-solar-fill`. Minimal's `--check` is now warning-free.
    - **Dark mode:**
      - `[data-bs-theme="dark"] a:not(.meter)`: the hierarchy's meter cards
        keep their own text colours;
      - the building-performance h4s use `var(--color-dark)`;
      - its note box is the `.performance-note` class, with a dark variant.
    - **Floor summary tint:** it's the blue its comment names,
      `rgba(39, 180, 232, 0.04)`; it was yellow `rgba(231, 243, 57, …)`.

    Verified, old engine vs new: `style.css`, `meters-hierarchy.css` and
    `font.css` change on every site, and minimal's
    `building_performance.htm` changes. `stylediff.py` on the three sites
    (222 renders) and 44 St Peters pages (88 renders) finds only:
    - the floor summary tint (light);
    - the hierarchy meter cards' text in dark mode (now white or their
      utility's light colour, not `rgb(222, 226, 230)`);
    - minimal's building-performance headings and note in dark mode;
    - minimal's solar header and hierarchy card, now green;
    - on switchboard and riser pages, the removed zero-width `::before`s
      (and never-drawn ones on `img`) and the card's `grid-column`.

    No element's box moves anywhere. No available site renders a schematic,
    so the blue schematic overlays aren't shown in a render.
19. **meter-templates.js on incomer, home and schematic pages, a bug fix
    from the JS investigation, approved and accepted 2026-10-22.** The
    release note for it: `incomer.html.j2`, `home.html.j2` and
    `schematic.html.j2` load `meter-templates.js`. Their `data-meter-id`
    values never resolved before and stayed "Loading...": an incomer's
    `meter_id` summary cards, a `live_value` extra with a `meter_id`, a
    schematic's meter overlays. A site template that overrides one of these
    pages keeps its own scripts. Verified, old engine vs new on all three
    sites:
    - only the incomer and home pages change (site1 1, campus 5, minimal
      4), each by gaining that one script line and its comment;
    - in headless Chromium, with a stub standing in for the controller's
      `/js/` libraries, every `data-meter-id` element on them (5, 8, 8)
      gains its `data-bacnet` address and binds. Nothing else in their DOM
      changes.
20. **sidebar.js rewritten without Popper, owner-approved from the JS
    investigation, accepted 2026-10-22.** `sidebar.js` was the pro-sidebar
    template's webpack development bundle: 164,616 bytes (24.5 KB gzipped),
    most of it Popper 2, used only to place the collapsed sidebar's pop-outs.
    It's now a plain script of 13,986 bytes (3.6 KB gzipped). It keeps the
    template's slide, collapse and toggle code, and places each pop-out with
    Popper's steps cut down to the template's options: `right`, `fixed`,
    flip to `left`, preventOverflow on the vertical axis, DPR rounding. It
    writes the same inline styles and `data-popper-placement`. It only
    places pop-outs while the sidebar is collapsed: expanded, the CSS
    overrides them. It assumes no ancestor of the sidebar has a transform.
    Verified, old engine vs new on all three sites:
    - only `sidebar.js` changes;
    - `stylediff.py`: identical on all 37 pages (222 renders, menu expanded);
    - a headless-Chromium probe drives the menu: open a sub-menu, collapse,
      open each pop-out and any inner sub-menu, click outside, expand,
      toggle. At 1920×1080, 1280×720, 1024×420, 1400×300 and 700×500, it
      records every pop-out's box, visibility, display, placement and
      inline style, with CSS transitions off. These are identical on 2 pages
      per site and 3 St Peters corpus pages (16 sub-menus, nested; given the
      current CSS), after a resize event. Without one, the only difference
      is one St Peters state where the old bundle also differs from itself:
      headless virtual time renders no frames, so ResizeObserver fires
      unpredictably. In real time (load held open by a slow image), old and
      new match there too, the pop-out re-centring as it shrinks.
21. **live-points.js tidied, owner-approved from the JS investigation,
    accepted 2026-10-22.** The release note for it: points bind in a
    zero timeout after DOMContentLoaded, not 500 ms later. That's still
    after every DOMContentLoaded handler on the page, which
    `meter-templates.js` and `energy-dials.js` need. Each value element has
    one MutationObserver (`onValueChange`), shared by its formatter and its
    freshness tracking, not two. **To confirm on a controller:** that the
    Optergy libraries need no time of their own after DOMContentLoaded (they
    load synchronously in `<head>`). Also, a site page script that creates
    `data-bacnet` elements later than DOMContentLoaded no longer gets the
    500 ms grace. The context-menu CSS stayed in `live-points.js` until the
    floor-layout work in `style.css` was done (see Open items). Verified,
    old engine vs new on all three sites:
    - only `live-points.js` changes;
    - in headless Chromium, with a stub for the controller's `/js/`
      libraries that writes each value 50 ms after binding, all 37 pages
      render an identical DOM at 3 s: formatted values, status icons,
      freshness classes and titles;
    - the first point binds 60 ms after DOMContentLoaded, not 516 ms.
22. **Dead `.layout.rtl` rules removed, owner-approved, accepted
    2026-10-22.** `style.css` goes from 58,481 to 57,554 bytes. Nothing in
    the engine or any site sets class `rtl`. The 10 rules only counted as
    used in `test_css_used` because the old `sidebar.js` bundle contained
    Popper's `direction === 'rtl'`, which re-baseline 20 removed. Verified,
    old engine vs new: only `style.css` changes, and `stylediff.py` finds no
    difference on all 37 pages (222 renders).
23. **Floor-layout CSS, owner-approved, accepted 2026-10-23.** `style.css`
    goes from 57,554 to 57,981 bytes. It gains `.floor-grid-cols-1/2/4`
    (`floor_page.meter_columns` other than 3) and `.floor-summary-plan-img`
    (`floor_page.floorplan: top`). The comment on the media query after them
    now says "grid rules", not "base rule". Verified, old engine vs new on all
    three sites:
    - the `_baseline/` copies match the old goldens, and only `style.css`
      changes;
    - its diff is those insertions and the two reworded comment lines;
    - no other built file uses the new classes, so no element's style changes.
24. **Guarded skeleton lines become generated blocks, owner-approved
    (section 6 fixes), accepted 2026-10-23.** Release note: every site's
    `sidebar-template.js` and `live-points.js` change. `sidebar-template.js`
    gains a `SIDEBAR_RUNTIME` block (`const SIDEBAR_RUNTIME_SRC`, the
    page-relative `sidebar.js` URL; a building folder's copy gets `../`), read
    by `script.src`. `live-points.js` gains an `OVERRIDE_FILE` block
    (`const LIVE_POINTS_OVERRIDE_FILE`, from `optergy_override_display`, now
    JSON-quoted, so it may hold a quote), read by
    `LivePointContextMenu.OVERRIDE_FILE`. They replace the build's two
    exact-shape line rewrites (`SIDEBAR_RUNTIME_SCRIPT`,
    `jsblocks.set_string_property`). A site's own copy of either file needs
    the new block. Verified, old engine vs new on all four sites:
    - only every `sidebar-template.js` (root and building folders; the tenant
      menus are templates) and every `live-points.js` change;
    - each by the new block and its comment, the one line that reads it, and
      in `live-points.js` the moved override comment;
    - Node evaluates each new value to the old literal
      (`js/project/2.0/sidebar.js`, `../js/project/2.0/sidebar.js`, `''`).
25. **Switchboard and riser diagrams built from meter cards, owner-requested
    and approved, accepted 2026-10-23.** Release note: every site's
    `switchboard-widget.css`, `meter-templates.js` and `switchboard-gauge.js`
    change, and so does every board and riser page. The pages drop the
    generated SVG background and the positioned overlays (`data-position`)
    for a single-line diagram laid out by CSS: the incomer on top feeding the
    busbar, the ways below it `columns` (default 5) to a row; a riser is a
    vertical busbar with a row per floor and its own meter at the bottom.
    Each meter is one `<div data-meter-card>` placeholder that
    `meter-templates.js` fills from METER_REGISTRY: live kW, a gauge against
    its rating, its CT, and a green or red glow from its status point. The
    lines are dark grey, white in dark mode. A riser is one page,
    `riser_<id>.htm` (no `_pN` split). A `bus_tie` is a coupler (`normally:
    open|closed`, optional `meter`) drawn on both boards it joins; a board fed
    from another says so and that way links to it; a way that is a riser
    links to its page. `layout:` and `floors_per_page:` are ignored and
    `--check` says so; the campus example's data loses them. Verified, old
    engine vs new on all four sites:
    - site1, minimal and tower change only those three runtime files. No page
      loads them except `meter-templates.js` on floor pages, and its change
      is purely additive (+97/−0) and acts only on `data-meter-card`
      elements, which those pages have none of;
    - campus: both boards show the same meters with the same ratings, the
      riser the same meters on one page; its three sidebars change only the
      riser link (`riser_4_p1.htm` → `riser_4.htm`); the four SVGs are gone;
      the north board gains the coupler mirrored from the south board's tie
      and a link on its riser way.
26. **Switchboard and riser diagrams restyled, owner-requested and approved,
    accepted 2026-10-24.** Release note: every site's
    `switchboard-widget.css`, `meter-templates.js` and `switchboard-gauge.js`
    change, and so does every board and riser page. A card shows its load as
    an accent stripe down its left edge (grey until the first reading, then
    green, amber or red, replacing the status dot and the warn/alarm border)
    and as a share of its rating beside a thinner gauge (the real share, past
    100% too); its CT is a chip, and the green comms glow is subtler (red
    unchanged). The incomer's card is larger and tinted. The diagrams sit on
    a dot-grid canvas, centred, under a key of the load colours and the comms
    glow (`diagram_legend` in `macros.j2`, Bootstrap utilities). A riser is
    drawn as a section through the building: floor names left of the busbar,
    taps right of it, dashed floor slabs between. On diagram pages the
    layout's flex columns may shrink (`:has(.sld, .riser)`), so a wide board
    scrolls in its card instead of widening the page. Line colours are
    unchanged. Verified, old engine vs new on all four sites:
    - only those three runtime files change on every site; `meter-templates.js`
      only inside its `data-meter-card` block, which no other page uses;
    - campus's three diagram pages change only by the key and, on the riser,
      the `riser-diagram` wrapper and the re-indentation inside it;
    - screenshots of campus's boards and riser in both themes, at 1100, 1700
      and 1920 px, with mock live values.

The example goldens changed only when the examples themselves changed; that's
logged in each example's `golden/CHANGELOG`.

---

## 6. Things that will bite you

Each of these now has a guard (2026-10-23); what's left is knowing why it's there.

- **Data file paths.** Read a data file through `site_data.data_path("x.yaml")`,
  never `DATA_DIR / "x.yaml"`: a site's file may be numbered (`04_x.yaml`).
  `site.yaml` is `site_data.BUILDING_FILE` (`data/00_site.yaml`, or the root
  `site.yaml` of an older site; `site_data.site_file()` finds it).
  Meters go through `site_data.read_meter_rows()`, which picks `meters.yaml` or
  `meters.csv`. Guard: `test_engine_conventions` fails on a join onto the data
  directory outside the path helpers.
- **The configured site lives in `site_data`.** `configure()` sets its paths
  and settings after import, so code reads them as `site_data.SITE_DIR`, not
  a name imported from it. `build.py` and the module files import
  `site_data`; a module file never imports `build` (`test_engine_conventions`),
  so there's no import cycle, no lazy import and no second copy of the state
  when `build.py` runs as a script. `build.<name>` still reads anything in
  `site_data`, but setting `build.SITE_DIR = …` only hides it: set values on
  `site_data`.
- **Undefined template variables fail the build** (`StrictUndefined`). Guard
  genuinely optional fields with `|default(...)`, `is defined` or `.get()`, or
  give them their default in the reader. Pages render through
  `render_page(template, ctx)`, which stops the build when a context key is
  named like a template global (`building`, `floor_page`, `slot`, …): builders
  pop placement fields such as `building` first. `test_engine_conventions`
  fails on a `.render(**ctx)` that bypasses it.
- **Paths:** template and data URLs are written relative to the site root.
  `relative_url(url, folder)` rewrites them for campus building folders. Every
  page gets `path_prefix` (`render_page` defaults it to `""`); write asset URLs
  as `{{ path_prefix }}…`, or `{{ _pp }}…` in templates extending
  `base.html.j2`. `test_engine_conventions` checks every template's
  `src`/`href`.
- **Generated JS blocks.** The build writes eight marker blocks into the staged
  JS (`jsblocks.py`), including `SIDEBAR_RUNTIME` (where a building folder's
  `sidebar-template.js` loads `sidebar.js` from) and `OVERRIDE_FILE`
  (`live-points.js`), which replaced the two exact-shape line rewrites in
  re-baseline 24. A site's own copy of a skeleton JS file needs its blocks.
- **Keep `_assets/` site-neutral.** Never paste a built block back into it.
  `test_engine_neutral` checks that the blocks are empty (or at their
  default), that no client names appear anywhere in the engine, the examples
  or the hook, and that engine code (outside comments) holds no literal
  BACnet addresses. The owner's four old-layout examples are its one named
  exception (`KNOWN_CLIENT_LINES`), until the template split. The
  pre-commit hook runs it.
- **`--check` runs a trial build.** It builds the site's modules into a temp
  dir and checks what got rendered, so a template the site overrides or never
  renders isn't checked against its data. The engine's templates are covered by
  the examples instead: `test_template_coverage` fails when no example renders
  one (dials and energy flow wait for d3). `--check` treats `/docs/<path>` as
  `<output root>/<path>`, because Optergy serves `project/` at `/docs/`
  (`linkcheck.DEPLOY_ROOT`).
- **Re-baselining:** `regress.py snapshot` refuses to overwrite a golden
  without `--accept "<reason>"`. Start the proof from `regress.py diff
  --against HEAD` (old engine vs new on every site), keep each re-baseline the
  only change in its step, and turn on the pre-commit hook
  (`git config core.hooksPath .githooks`) so an output change can't be
  committed without its golden. `check` won't diff against a stale
  `_baseline/` copy.
---

## Open items

<a id="next-steps"></a>**Next steps: CSS and Bootstrap (owner, 2026-10-21).** The owner keeps the
full Bootstrap CSS and prefers its classes over `style.css`'s. Steps 1–3 of the CSS
plan are done: `_build/stylediff.py` (README "What a change looks like"),
`tests/test_css_used.py`, re-baselines 15 and 16. Still to do, each its own
re-baseline with the owner's go-ahead:
1. **Step 4, done (re-baseline 17).** The card shell, header strip and hover bar
   weren't merged: they differ in more than one value. The flex patterns that repeat
   most (`display: flex` + `align-items: center`, 19 rules) belong to item 3.
   - **Coverage corpus** for any CSS step: the St Peters site in git `HEAD` renders
     what the examples don't (risers, switchboards, dials, energy flow, building
     performance). `git archive HEAD site | tar -x -C <scratch>`, mark its "Rising
     BusBar" meters `function: Riser-meter` in the scratch copy so the riser pages
     build, and build it with `--modules` = every module but `pages` (its frozen
     pages clash with the switchboards). Build it with the engine before and after,
     then run `stylediff.py --pages` on a sample. Keep it out of the repo.
2. **Visible fixes, done (re-baseline 18).**
3. **Bootstrap classes in the markup.** How to find candidates: compare each project
   class's rule with Bootstrap rules of identical values (1rem = 16px). Constraints:
   - Utilities are `!important`. Swap a declaration only where no state, `@media`,
     dark-mode or compound rule on the same element sets that property.
   - Bootstrap's spacing is 4/8/16/24/48px, and its breakpoints are 576/768/992/1200/1400.
     The project's 5/6/10/12/15px spacing and its 480/1024/1600 breakpoints have no utility.

   First exact matches:

   | Project class | Bootstrap |
   |---|---|
   | `.floor-stats-subheader-flex` | `d-flex justify-content-between align-items-center` |
   | `.performance-content` | `d-flex flex-grow-1 align-items-center justify-content-center` |
   | `.floor-summary-row` | `d-flex justify-content-center position-relative` |
   | `.search-wrapper` | `position-relative` |
   | `.content` | `vh-100 overflow-hidden`; check its `@media` rules |

   Not safe as utilities:
   - `.summary-card-value` (`fs-6 fw-semibold text-end`): its size changes at ≤575.98px.
   - `.tab-content` (`.active` switches `display`).
   - `.floor-stats-group` (`mt-1`): `margin-top` is set elsewhere.

   The markup lives in templates, `macros.j2` and the runtime JS (`meter-templates.js`,
   `reports.js`, the sidebar, `meter-hierarchy.js`). Prove each conversion with
   `stylediff.py`; it matches elements by order, so class changes show as class lines.

   Bigger options:
   - the Bootstrap grid for `grid-cols-N` and `performance-columns`: unstyled today,
     they stack, so this is a visible change;
   - Bootstrap themed from the palette: `:root,[data-bs-theme=light]{--bs-…}`, then
     the dark values;
   - components (card, nav-pills, form-control), only with variable overrides.

**JS: what's left of the investigation (owner, 2026-10-22).** Done:
re-baselines 19–22 and `--check`'s warning for a page missing the runtime
script its markup needs (`linkcheck.unloaded_scripts`). The owner ruled out
`defer` on the Optergy `/js/` libraries. Still open, each its own step:
- **Find out on a controller:** whether it gzips `/docs/` and what cache
  headers it sends (DevTools Network: `Content-Encoding`, `Cache-Control`,
  `ETag` on a project script); whether `liveDisplayAndDashboard.js` batches
  its polling (Network, Fetch/XHR, on `meters_hierarchy.htm`: about 56
  requests every 10 s means one per point); and that points still bind
  with re-baseline 21's shorter start.
- **Page changes (re-baselines):** a content-hash `?v=` on project JS and
  CSS (an optional site.yaml setting); the saved-theme snippet inline in
  `<head>`, so dark mode doesn't flash light; the build picking each page's
  scripts from its markup, not each template.
- **Later, if the controller doesn't gzip:** every page ships the whole
  site's report URLs (`reports.js`) and meter registry (`meter-templates.js`,
  with placement fields the runtime never reads). That's small for site1
  and large for a 47-floor tower (542 KB and 212 KB).
- **Small:** move `live-points.js`'s context-menu CSS into `style.css`
  (no longer blocked: the floor-layout work there is in); when d3
  lands (below), ship only the d3 modules dials and energy flow use.

**Rest of Phase 7.** The project CSS and fonts are in (re-baseline 7). Still owed, for `_assets/`
unless noted; `build.py --check` lists the ones a site references:
- `js/d3/7/*`: d3.v7.min.js, d3-sankey.min.js, energy-charts.js (dials, energy_flow).
- `placeholder.png`, loaded by `report-template.js` (`--check` can't see it).
- The owner's `examples/1lb`, `2ml`, `4ml`, `6hl` (old `building.yaml` layout) carry
  client names, and `examples/` ships with the template. Kept for now (owner,
  2026-10-23): `test_engine_neutral`'s `KNOWN_CLIENT_LINES` excuses exactly
  their 8 lines. Remove, rework or move them, and drop that list, before the
  template split.

**Housekeeping:**
- Delete `_build/migrate_js_data.py` once Phase 2 is committed. It reads git `HEAD`.
- `todo.md` was removed from the working tree. Its item, the n/a quoting bug, is fixed.
- The `site_data.py` split is done (2026-10-23): `site_data.py` (about 1,030
  lines) holds `configure()`, the readers and page locations; `build.py`
  (about 1,900) keeps staging, layout, the builders, the menu and `--check`,
  which stayed because it runs the trial build.

<a id="site1"></a>**site1, built from the meters export alone.** To fill in:
- **Confirm** the BACnet device (300) and offsets (Modbus 40, Calculation 82) in
  `00_site.yaml`: copied from St Peters' controller conventions. The footer
  contact is a placeholder (`facilities@example.com`).
- **Floorplans** for its six levels, `site/assets/img/floors/floor_<key>.png`
  (`--check` lists them).
- **The export itself:** each floor's distribution-board card is titled "1",
  the CSV's zone; meter 394 (5th floor total) has no utility; 1st floor isn't
  in it ("Floor 01 Total Electricity" sits on `ground`).
- **Reports** (`14_reports.yaml`): each level's Demand and Consumption charts
  plot its total meter (the basement has none; DB/L/B2-Total, 373, stands in).
  Placements have no library item `id`, so the cards link to `#`: add the ids
  once the reports exist in the controller's library.
- **Tenants** (`05_tenants.yaml`): three dummy tenants until the real ones
  are known. Their menus link the default Docs PDF,
  `tenants/<slug>/docs/<slug>-submetering.pdf`, which the build can't fill
  (3 `--check` warnings). Each tenant's `docs:` fixes it: a PDF in
  `site/assets/`, a URL, or `false`. Setting it changes site1's tenant
  sidebars, so it's a re-baseline for the owner to approve.
- **Not built yet** (no data in the export): home page, named points, floor
  summary-card points, switchboards, risers.

**Engine limitations still open:**
- **Still site-wide on a campus:** `building_performance` (NABERS points are
  named site-wide) and `schematics`. The status-icon image paths in `macros.j2`
  are root-relative; fine while their pages are root-only.
- **Utility colours:** a new utility needs only a `.meter-<code>` CSS rule.
  Zone headers get their class from the meter's code (see re-baseline 6).
  `meter-templates.js` falls back to `electricity` for a meter with no utility.
- **Energy flow:** the Sankey topology (Tenants/Landlord/Gas/Boilers) is still
  hardcoded in `build_energy_flow`. Only St Peters' data shape fits it.
- **Asset checks:** the `--check` `.meter-<code>` CSS-class check is skipped
  until the project CSS exists. Missing-file checks now cover pages, sidebars,
  images, scripts and CSS `url()`s. They don't cover URLs built in JS at
  runtime (e.g. `placeholder.png`).
- **Engine `building_performance.html.j2`** still hardcodes "NABERS UK" text,
  and "N/A" for district heating/cooling and water.

---

## 7. Next steps (from the approved plan)

### Phase 7: what's left
Done: site-neutral `_assets/`, placeholder images, client-string test,
`data-point` engine template, missing-asset/link reporting in `--check`.
Still to do:
- **Once the owner adds the missing assets:** run `--check` until it shows
  only the known St Peters data issues. Drop the `css/project/` exemption in
  `test_check.py`. Run `regress.py check`; adding `_assets/` files St Peters
  references changes its output, so that's a re-baseline: accept it with a
  reason.
- **Template split, run by the owner** (after the assets are in). The engine
  paths below were verified on their own: a scratch copy of them passes both
  example goldens and all tests.
  1. Create a fresh template repo holding only the engine paths:
     ```bash
     mkdir ../ems-template && cd ../ems-template && git init
     cp -r ../build_system/{_build,_templates,_components,_assets,examples,tests,.githooks,requirements.txt,.gitignore,README.md} .
     rm -f _build/migrate_js_data.py && find . -name __pycache__ -prune -exec rm -rf {} +
     python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
     git config core.hooksPath .githooks
     .venv/bin/python _build/regress.py check && .venv/bin/python -m pytest -q tests/
     git add -A && git commit -m "EMS build engine"
     ```
     Not copied: `site/`, `HANDOFF.md`, `CLAUDE.md` (it describes this repo's site; the
     template wants its own, engine-only one), `_baseline/`, `project/`.
  2. In this repo: `git remote add template ../ems-template`, `git fetch template`, then
     `git merge --allow-unrelated-histories -s ours template/main`.
  3. From then on: `git pull template main`, then `regress.py check`, then review.

### Phase 8: docs (done 2026-10-03)
- `README.md` (site-neutral; it ships with the template):
  - quick start, and starting a new building;
  - how a build works;
  - reference for `site.yaml`, `meters.csv`, `floors.yaml` and every module's
    data file;
  - the modules table and how-tos;
  - `--check`, regression and the upgrade workflow.
- `test_engine_neutral` now also scans `README.md`, `requirements.txt` and
  `.gitignore`.
- Stale comments fixed:
  - `building.yaml` → `site.yaml`;
  - `todo.md` references;
  - the removed `SUMMARY_CARD_ROLES` in `site/data/bms_bindings.yaml`;
  - "build_tenants() isn't called" in `site/data/tenants.yaml`;
  - legacy page names in the `page.html.j2` / `build_pages` docs.

  No output changed.
- Upgrade workflow, corrected: a new site **clones** the template, so it
  shares the template's history. Only this repo, whose history predates the
  split, needs the one-time `-s ours` merge.

---

## 8. Pointers

- **Approved plan** (outside the repo): `~/.claude/plans/tranquil-crunching-pebble.md`.
  Sections 1, 6 and 7 above carry the parts that matter.
- **Re-baseline audit trail:** `site/golden/CHANGELOG`, `examples/*/golden/CHANGELOG`.
- **Data file headers:** most files in `site/data/` start with a comment block
  describing their schema.
