# build_system

This repo holds an engine that builds an Optergy EMS dashboard (static `.htm`
pages plus generated runtime JS blocks) from a site directory. St Peters, the
reference site, lives in `site/`. Everything outside `site/` is **engine**;
it becomes the starter template that every other building forks.

- `README.md` is the engine reference: every site file and field, the modules,
  `--check`, and the regression and upgrade workflows. Read it before changing
  site data, a template or a module.
- `HANDOFF.md` is the templatisation history: approved re-baselines, St
  Peters' known data issues and the open items. Read it before any re-baseline,
  or when asked why something is the way it is.

## Done means

Run these with `.venv/bin/python`:
1. `_build/regress.py check`: every golden identical.
2. `-m pytest -q tests/`: green.
3. `_build/build.py --check`: 0 errors. St Peters' known warnings are listed
   in HANDOFF.md.

## Goldens are the regression bar

St Peters' output stays **byte-identical**. Any change to a site's output is a
**re-baseline**:
- A St Peters re-baseline needs the owner's approval before you make it.
- Make it the only change in its step.
- Decide the proof first, e.g. "identical once comments are stripped" or
  "only these files changed". Verify it, then accept with
  `_build/regress.py snapshot --site <dir> --accept "<reason, including the proof>"`.
- Example goldens change when the examples themselves change. Accept those
  the same way, with a reason.

Refactors keep every golden identical. When they don't, `regress.py check`
prints the diff.

## Engine and site

- **Building data lives in `site/`:** `data/`, `pages/`, template overrides
  in `templates/`, and `assets/`. The engine stays **site-neutral**:
  `tests/test_engine_neutral.py` catches client names, and literal BACnet
  addresses in engine code. The examples use invented data.
- **Data flows one way:** site files → build → `project/`. `project/` is
  regenerated on each build and gitignored, so edit the source files. The
  generated JS blocks in `_assets/` stay empty; the build fills its staged
  copy.
- **A one-off addition** to a standard page is an extra: a component placed
  in a slot through `site/data/extras.yaml`. Use the `html` component for
  anything new, and make it a component once it recurs (README "Extras").
- **St Peters-only changes to existing markup** go in `site/templates/`, as
  an override with the same name. An **engine fix** goes in `_templates/`,
  `_build/` or `_components/` and must keep St Peters byte-identical.
- **St Peters' frozen pages** (`site/pages/`) stay frozen. Its known data
  issues get fixed one reviewed re-baseline at a time.

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

- **Data files are numbered** in fill-in order (`site/data/03_meters.yaml`;
  README "Data files and the order to fill them in"). Engine code opens them
  with `build.data_path("<name>.yaml")`, finds `site.yaml` (`data/00_site.yaml`)
  as `build.BUILDING_FILE`, and reads meters with `build.read_meter_rows()`. St Peters' meters are `03_meters.yaml`, laid out
  level → core → meter; a new CSV export comes in through
  `_build/import_meters.py`.
- **Templates use `StrictUndefined`.** Guard optional fields with
  `|default(...)` or `is defined`. Builders pop any `building` key from a
  page's context, because it would shadow the `site.yaml` global.
- **URLs:** templates write asset and page URLs as `{{ _pp }}…`; `site/pages/`
  fragments write them as `{{ path_prefix }}…`. That prefix supplies the
  `../` a campus building folder needs.
- **Module imports:** `build_switchboards.py` and `build_risers.py` do
  `import build`. `build.py` imports them lazily, and its `__main__` runs the
  importable `build` module so they share its configured state. A new module
  file follows the same pattern.
- **Guarded skeleton lines:** the build rewrites two lines by their exact
  shape, and stops if either shape changes:
  `script.src = "js/project/2.0/sidebar.js";` in `sidebar-template.js`, and
  `OVERRIDE_FILE: '…',` in `live-points.js`.

## Working with the owner

- Leave every change uncommitted in the working tree; the owner reviews and
  commits by hand.
- Finish each piece of work with the "done" checks and a summary of what
  changed, for review.
