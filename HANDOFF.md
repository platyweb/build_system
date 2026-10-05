# Handoff: templatising the EMS build system for any building

**State as of 2026-10-03:** phases 0–6 and 8 are done. Phase 7 is done except
for the parts that need the missing assets (see [Open items](#open-items)).
**`README.md` is now the engine reference.** It covers every site file, the
modules, how-tos, `--check`, regression and the upgrade workflow. This
handoff keeps only the history and the open items for this site.
**Nothing is committed.** Everything sits in the working tree on top of
`ae4d7f0` for manual review and commit. Last verified state:
- `python _build/regress.py check`: all **4 goldens identical**. In Phase 7,
  St Peters changed only through the two owner-approved JS re-baselines (5 and
  6 below). The example goldens were also re-snapshotted for their own example
  changes. Every reason is logged in the CHANGELOGs;
- `pytest`: **64 passed**;
- `build.py --check`: passes with 12 warnings. They're the known St Peters
  items plus the missing assets (see [Open items](#open-items));
- **template split dry run:** a copy of only the engine paths (no `site/`)
  passes both example goldens and all 64 tests, with no client names.

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

**St Peters is the reference site.** Its generated output must stay
byte-identical through every phase, except for explicitly approved re-baselines.

### Decisions made with the owner (don't relitigate)
| Topic | Decision |
|---|---|
| Repo model | Starter template, one repo per site. **This repo becomes St Peters' site repo**; the template is split off as a fresh repo in Phase 7 |
| Meter source of truth | `site/data/meters.csv`. The `METER_REGISTRY` that used to be committed in the JS had drifted (129 of 652 rows) and was discarded |
| Data flow | Site data files → build → JS. The build never reads data back out of JS |
| Regression bar | St Peters byte-identical every phase. Re-baselines only when pre-approved, each the only change in its step, logged in `site/golden/CHANGELOG` |
| St Peters' frozen pages | Risers, switchboards, tariffs, system and landlord pages stay frozen HTML in `site/pages/`. Data-driven generators serve new sites |
| Campus layout | One subfolder per building (`<slug>/<building>/…`). Single-building sites keep flat filenames |
| Git | **No commits by the assistant.** The owner reviews and commits manually |

---

## 2. Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # jinja2, pyyaml, pytest

.venv/bin/python _build/build.py                           # full build of site/ → project/st-peters/
.venv/bin/python _build/build.py floor_23rd                # rebuild one page into the existing output
.venv/bin/python _build/build.py --check                   # validate site data + a trial build (temp dir); writes nothing
.venv/bin/python _build/build.py --site examples/campus --out /tmp/out   # build another site elsewhere
.venv/bin/python _build/build.py --modules switchboards    # override site.yaml modules for one run

.venv/bin/python _build/regress.py check                   # every site's fresh build vs its golden
.venv/bin/python -m pytest -q tests/                       # unit tests + the golden check
```

Notes:
- **Node is used** for `node --check` on the generated JS; it's skipped if absent.
- **`project/` is fully regenerated** on every full build. The build only wipes
  a directory it created (`project/.build-output` marker).

---

## 3. Repo layout

```
_build/build.py              engine: configure(), readers, layout derivation, builders, MODULES, --check, CLI
_build/jsblocks.py           renders/injects generated JS blocks (METER_REGISTRY, POINTS, BACNET_CONFIG, REPORT_URLS, SIDEBAR_HTML)
                             + set_string_property (live-points.js OVERRIDE_FILE)
_build/linkcheck.py          --check's output checks: data-point/meter ids on built pages; referenced-but-missing files
_build/generate_meter_registry.py   meters.csv reader + normalisers (name is historical: it no longer generates anything itself)
_build/build_switchboards.py, build_risers.py   the `switchboards` / `risers` modules (run(env, only))
_build/regress.py            golden regression harness (multi-site)
_build/migrate_js_data.py    ONE-OFF (Phase 2): JS → YAML migration. Never committed. Delete after committing Phase 2
_templates/                  engine templates + partials/macros.j2
_assets/                     engine runtime skeleton (project JS, vendor libs, generic images). Copied into every build.
                             Site-neutral: its generated blocks are empty (the build fills the staged copy)
site/                        St Peters — everything specific to this building
  site.yaml                  identity, modules, bacnet, utilities, summary_roles, floor_page, tenant_page (buildings: n/a)
  data/                      floors.yaml (level roster), meters.csv, incomers, sidebar, pages, tenants, switchboards,
                             risers, energy_flow, dials, meters_hierarchy, bms_bindings, points, reports, schematics
  pages/                     frozen page fragments (<key>.body.html …)
  templates/                 overrides of _templates/ (incomer_electricity, building_performance)
  assets/img/                St Peters images overlaid on _assets/ (floorplans, LV/riser SVGs, logos, sidebar photo)
  golden/                    regression manifests + CHANGELOG
examples/minimal/            "Acme Depot": single storey, electricity/solar/gas/water, building performance, no tenants (+ golden)
examples/campus/             "Riverside Campus": 2 buildings, subfolders, switchboards with cross-building bus tie (+ golden)
                             (both have placeholder floorplans in assets/img/floors/)
tests/                       test_golden (wraps regress check), test_jsblocks, test_levels, test_site_config, test_campus,
                             test_check (--check), test_engine_neutral (no client data in engine/examples)
_baseline/                   (gitignored, ~45 MB) full copy of each last golden build. Used only to print readable diffs
```

---

## 4. How a site is described (cheat sheet)

**`site.yaml`.** The full examples are `site/site.yaml` (office tower),
`examples/minimal/site.yaml` and `examples/campus/site.yaml`.

| Key | Meaning |
|---|---|
| `slug` | Output dir `project/<slug>/` |
| `name`, `short_name`, `ems_name`, `postcode`, `net_internal_area` | Identity (`building.*` in templates) |
| `modules` | Page families to build: `floors incomers home meters_hierarchy schematics building_performance pages tenants energy_flow dials switchboards risers sidebar` |
| `buildings` | Campus only: `[{key, name}]`. More than one → per-building folders |
| `utilities` | `{code: {label, kind: electric\|thermal\|other}}`. The code is the CSS class `.meter-<code>` |
| `bacnet` | `{device, power_offset: {<meters.csv type>: <offset>}}`. Address = `<device>\|<objtype>\|<instance>\|85\|-1` |
| `optergy_lib_version`, `brand`, `footer` | Controller lib cache-bust, sidebar header/footer |
| `optergy_override_display` | Optional. The Optergy display file that live-points.js point overrides post to (`OVERRIDE_FILE`). Blank if unset |
| `summary_roles` | Summary-card catalog `{role: {title, format}}`. Live point from `bms_bindings.yaml` by (role, floor) |
| `floor_page` | `tabs` (`[{id, label, slot, roles}]`), `summary_cards` (`total`/`tenants`/`landlords` → meters.csv `function`), `centre_zone`, `zone_suffix`, `zone_subtitles`, `report_titles`, `summary_label`, `riser_card_link` |
| `tenant_page` | `summary_label`, `tabs` (subset of floor_page tab ids) |

**`data/floors.yaml` is the level roster:**
- One `floor_<key>:` entry per level, **bottom → top**; file order is the
  physical order.
- Optional fields: `label`, `nav_label`, `heading`, `page: false`, `building`.
- Any other field is page data (e.g. `floorplan_tab`).
- Every floor named anywhere else must be a level here; `--check` enforces it.

**`data/meters.csv`** columns:
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

The example goldens changed only when the examples themselves changed; that's
logged in each example's `golden/CHANGELOG`.

---

## 6. Things that will bite you

- **Two copies of `build`.** `python _build/build.py` runs `main()` on the
  importable `build` module, not on `__main__`. Without that, the switchboard
  and riser modules (`import build`) would see a second, unconfigured copy.
  The guard is at the bottom of build.py. Those modules are imported lazily
  (`_switchboards`/`_risers` wrappers) because they import build back.
- **Undefined template variables fail the build** (`StrictUndefined`). Guard
  genuinely optional fields with `|default(...)`, `is defined` or `.get()`.
  Never pass a `building` key in a page's context: it shadows the `building`
  global (site.yaml). Builders pop it.
- **Paths:** template and data URLs are written relative to the site root.
  `relative_url(url, folder)` rewrites them for campus building folders. Use
  `{{ _pp }}` (templates) or `{{ path_prefix }}` (frozen fragments) for assets.
- **Per-folder sidebars** rewrite the runtime line
  `script.src = "js/project/2.0/sidebar.js";` (`SIDEBAR_RUNTIME_SCRIPT` in
  build.py). The build stops if that exact line disappears from
  `_assets/.../sidebar-template.js`.
- **`OVERRIDE_FILE` sits inside an object literal** in live-points.js, so it
  can't be a marker block. `jsblocks.set_string_property` rewrites that one
  line and stops the build if the line's shape changes.
- **Keep `_assets/` site-neutral.** Never paste a built block back into it.
  `test_engine_neutral` checks that the blocks are empty, that no client names
  appear anywhere in the engine or examples, and that engine code (outside
  comments) holds no literal BACnet addresses.
- **`--check` runs a trial build.** It builds the site's modules into a temp
  dir and checks what got rendered, so a template the site overrides or never
  renders isn't checked. It treats `/docs/<path>` as `<output root>/<path>`,
  because Optergy serves `project/` at `/docs/` (`linkcheck.DEPLOY_ROOT`).
- **Re-baselining:** `regress.py snapshot` refuses to overwrite a golden
  without `--accept "<reason>"`. Check determinism and acceptance criteria
  first, and keep each re-baseline the only change in its step.

---

## Open items

**Blocking the rest of Phase 7. The owner needs to add these to `_assets/` (git now tracks them).**
`build.py --check` lists the ones a site actually references, so re-run it to tick them off:
- `css/project/2.0/*.css`: style, diagrams, switchboard, switchboard-widget, sankey, dials, meters-hierarchy, tenant-accordion
- `js/d3/7/*`: d3.v7.min.js, d3-sankey.min.js, energy-charts.js
- SVGs: `riser_elec`, `riser_heat`, `chw_system`, `lphw_system`, `chw_tariff`, `lphw_tariff`, `lthw_tariff`, `nabers_calc`;
  and `placeholder.png`. `report_template`'s JS loads it, so `--check` can't see it.
- St Peters floorplans `floor_ground.png`, `floor_47th.png` (and `floor_Basement.png` if the tenants
  module comes on), for `site/assets/img/floors/`
- Once the CSS is in, drop the `css/project/` exemption in `tests/test_check.py`.

**Housekeeping:**
- Delete `_build/migrate_js_data.py` once Phase 2 is committed. It reads git `HEAD`.
- `todo.md` was removed from the working tree. Its item, the n/a quoting bug, is fixed.
- `build.py` is about 2,100 lines. The planned `site_data.py` split (readers +
  `--check`) wasn't done. It's optional.

**St Peters data issues, kept as-is to stay byte-identical. Fix each later as its own reviewed re-baseline:**
- **Broken or stale links.** `--check` now reports all of these:
  - `floor_page.riser_card_link` is `/docs/tlb/riser_overview.htm` (Leadenhall slug);
  - frozen fragments link `/docs/1sr/…`: riser_electricity, riser_heat, swb_lv01, swb_lv02;
  - the sidebar links `swb_lv03–08.htm` and `tenants.htm`, which aren't built;
  - the sidebar links 19 `/docs/tenants/…` pages. The tenants module is off, so
    they aren't built;
  - `/docs/manuals/*.pdf` (sidebar) and `/docs/meters/*.pdf` (docs_meters)
    aren't in the build. Presumably they're uploaded separately; confirm.
- **Wrong or duplicated points:**
  - frozen `swb_lv01` uses pre-renumber meter ids (its board's incomer is now meter 39);
  - `tariff_lthw` reuses `tariff_lphw`'s BACnet points;
  - `site/templates/building_performance.html.j2` uses `300|2|86` for the live
    rating, but `points.yaml` says `nabers_rating` is `300|2|99`.
- **Leftover or stale content:**
  - `system_lphw.tail_scripts.html` ships a debug coordinate overlay;
  - the home page text says "98 meters across 5 floors";
  - placeholder facts in `site.yaml` (postcode `TBD`).
- **Not finished:** tenants module off (tenant data not reconciled).
- **`--check` warnings:** 3 `bms_bindings.yaml` roles (`floor_demand_*`) aren't
  shown on any page. Their cards were computed but never rendered, and the
  dead code was removed in Phase 3.

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
     cp -r ../build_system/{_build,_templates,_components,_assets,examples,tests,requirements.txt,.gitignore,README.md} .
     rm -f _build/migrate_js_data.py && find . -name __pycache__ -prune -exec rm -rf {} +
     python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
     .venv/bin/python _build/regress.py check && .venv/bin/python -m pytest -q tests/
     git add -A && git commit -m "EMS build engine"
     ```
     Not copied: `site/`, `HANDOFF.md`, `CLAUDE.md` (it names St Peters; the
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
