# build_system

This repo holds an engine that builds an Optergy EMS dashboard (static `.htm`
pages plus generated runtime JS blocks) from a site directory. The building
being built lives in `site/`: today `site1`, built from its meters export
(`site/data/meters.csv`). Everything outside `site/` is **engine**; it becomes
the starter template that every building forks.

- `README.md` is the engine reference: every site file and field, the modules,
  `--check`, and the regression and upgrade workflows. Read it before changing
  site data, a template or a module.
- `HANDOFF.md` is the templatisation history: approved re-baselines, the
  site's known data issues and the open items. Read it before any re-baseline,
  or when asked why something is the way it is.

## Done means

Run these with `.venv/bin/python`:
1. `_build/regress.py check`: every golden identical.
2. `-m pytest -q tests/`: green.
3. `_build/build.py --check`: 0 errors. The site's known warnings are listed
   in HANDOFF.md.

## Goldens are the regression bar

The site's output stays **byte-identical**. Any change to a site's output is a
**re-baseline**:
- A re-baseline of `site/`'s golden needs the owner's approval before you make it.
- Make it the only change in its step.
- Decide the proof first, e.g. "identical once comments are stripped" or
  "only these files changed". Verify it, then accept with
  `_build/regress.py snapshot --site <dir> --accept "<reason, including the proof>"`.
- Example goldens change when the examples themselves change. Accept those
  the same way, with a reason.

Refactors keep every golden identical. When they don't, `regress.py check`
prints the diff. `regress.py diff --against HEAD` shows what an uncommitted
engine change does to every site, the starting point for a re-baseline's proof.

## Engine and site

- **Building data lives in `site/`:** `data/`, template overrides in
  `templates/`, and `assets/`. The engine stays **site-neutral**:
  `tests/test_engine_neutral.py` catches client names, and literal BACnet
  addresses in engine code. The examples use invented data.
- **Data flows one way:** site files → build → `project/`. `project/` is
  regenerated on each build and gitignored, so edit the source files. The
  generated JS blocks in `_assets/` stay empty; the build fills its staged
  copy.
- **A one-off addition** to a standard page is an extra: a component placed
  in a slot through `site/data/extras.yaml`. Use the `html` component for
  anything new, and make it a component once it recurs (README "Extras").
- **Site-only changes to existing markup** go in `site/templates/`, as an
  override with the same name. An **engine fix** goes in `_templates/`,
  `_build/` or `_components/` and must keep every golden byte-identical.

## Backward compatibility

An older site must keep building, with identical output, on a newer engine:
- **New settings are optional**, and their default reproduces today's output.
- **`_components/published.yaml` only grows**, enforced by
  `tests/test_components.py`. Rename a component option with `aliases:` and
  remove one with `retired:`. A component's required options and `one_of`
  groups never change, and an option's `choices` only grow.
- **A deliberate output change** to shared markup is a re-baseline for every
  site; say so in its release note.

## Gotchas

- **Data files are numbered** in fill-in order (`site/data/02_floors.yaml`;
  README "Data files and the order to fill them in"). Engine code opens them
  with `site_data.data_path("<name>.yaml")`, finds `site.yaml` (`data/00_site.yaml`)
  as `site_data.BUILDING_FILE`, and reads meters with `site_data.read_meter_rows()`:
  a site's meters are `meters.csv`, an export read as it is (site1), or
  `meters.yaml`, laid out level → core → meter. The tenant catalog is
  `05_tenants.yaml` (`site_data.read_tenants()`). `04_points.yaml` holds every BMS point, grouped by
  page (`named`, `floors`, `incomers`, `home`): read it with `read_points()`,
  `read_bms_bindings()`, `read_incomers()` and `read_home()`, never the file,
  since an older site keeps those in separate files.
- **`data/01_pages.yaml` is the menu** (README "data/pages.yaml"): it lists
  every page the site builds, and the build derives the modules and the
  sidebar from it (`build.read_menu()`). Read the sidebar with
  `build.sidebar_cfg()` and the site's own pages with `build.own_pages()`:
  an older site still has `sidebar.yaml`, `modules:` and a frozen `pages:` list.
- **Templates use `StrictUndefined`.** Guard optional fields with
  `|default(...)` or `is defined`, or give the field its default in the
  Python reader. Render a page with `render_page(template, ctx)`: it stops
  the build when a context key is named like a template global (`building`,
  `floor_page`, `slot`, …), so builders pop placement fields such as
  `building` first.
- **URLs:** every page gets `path_prefix` (`""` at the site root, the `../`
  a campus building folder needs). Write asset and page URLs as
  `{{ path_prefix }}…`; templates extending `base.html.j2` may use its short
  alias `{{ _pp }}…`. `tests/test_engine_conventions.py` checks the templates.
- **Module imports:** `_build/site_data.py` is the configured site:
  `configure()`, the paths and settings it sets, and every data reader.
  `build.py` and the module files (`build_switchboards.py`, `build_risers.py`)
  import it, and read the configured values as `site_data.SITE_DIR` etc.,
  since `configure()` sets them after import. A module file never imports
  `build` (`tests/test_engine_conventions.py`). `build.<name>` still reaches
  anything in `site_data` for reading; set values on `site_data` itself.

## Working with the owner

- Leave every change uncommitted in the working tree; the owner reviews and
  commits by hand.
- Finish each piece of work with the "done" checks and a summary of what
  changed, for review.
