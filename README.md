# EMS build system

Generates an Optergy energy-management dashboard for a building: static
`.htm` pages, plus the data blocks the dashboard's runtime JavaScript reads.
It's all built from one **site directory** of YAML and CSV that describes
the building. The output is copied onto the Optergy controller, which serves
it under `/docs/` and supplies the live values.

This repository is the **engine** plus two example sites. Each building lives
in its own repository, forked from this one, with its data in `site/`.
Engine upgrades are pulled in from here (see
[Upgrading a site](#upgrading-a-site-from-the-template)).

- [Quick start](#quick-start)
- [Handling differences between sites](#handling-differences-between-sites)
- [How a build works](#how-a-build-works)
- [The site directory](#the-site-directory): [`site.yaml`](#datasiteyaml), [fill-in order](#data-files-and-the-order-to-fill-them-in), [`pages.yaml`](#datapagesyaml), [`floors.yaml`](#datafloorsyaml), [`meters.yaml`](#datametersyaml), [`points.yaml`](#datapointsyaml), [`tenants.yaml`](#datatenantsyaml), [other data files](#other-data-files)
- [Modules](#modules)
- [Extras: one-off additions to pages](#extras-one-off-additions-to-pages)
- [How to…](#how-to)
- [Checking a site](#checking-a-site---check)
- [Regression testing](#regression-testing)
- [Backward compatibility](#backward-compatibility)
- [Upgrading a site from the template](#upgrading-a-site-from-the-template)

---

## Quick start

Needs Python 3.10+ (developed on 3.12). Node is optional; the regression
harness uses it to run `node --check` on the generated JS.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # jinja2, pyyaml, pytest

.venv/bin/python _build/build.py --site examples/minimal --out /tmp/ems   # build an example
```

| Command | What it does |
|---|---|
| `_build/build.py` | Full build of `site/` into `project/<slug>/` |
| `_build/build.py floor_L00` | Rebuild one page (by key) into an existing build |
| `_build/build.py --check` | Validate the site, then do a trial build in a temp dir and check it. Writes nothing |
| `_build/build.py --site DIR --out DIR` | Build another site, or build somewhere else |
| `_build/build.py --modules a,b` / `all` | Build these modules instead of `site.yaml`'s, for one run |
| `_build/regress.py check` | Compare each site's fresh build with its golden |
| `_build/regress.py snapshot --site DIR [--accept "reason"]` | Record or update a site's golden |
| `.venv/bin/python -m pytest -q tests/` | Unit tests + the golden check |

Run the `_build/` scripts with `.venv/bin/python`. A full build deletes and recreates its
output root, but only one it created itself (marked by a `.build-output`
file). It won't wipe a directory it didn't make.

### Starting a new building

1. Clone the template as the building's repo, keeping the template as a
   remote for upgrades:
   ```bash
   git clone <template repo URL> <building> && cd <building>
   git remote rename origin template && git remote add origin <building repo URL>
   ```
2. Start from the smallest example:
   ```bash
   cp -r examples/minimal site && rm -rf site/golden
   ```
3. Fill in `site/data/` in [number order](#data-files-and-the-order-to-fill-them-in):
   `00_site.yaml` (`slug`, `name`, `bacnet`, `utilities`), `01_pages.yaml`
   (the pages to build, laid out as the menu), `02_floors.yaml`,
   `03_meters.yaml` (or drop a meters export in as `data/meters.csv`),
   then the data files of the pages you listed.
4. Run `build.py --check` until it reports no problems, then run `build.py`.
5. Record the first golden with `regress.py snapshot --site site`, then commit.

Live values need the controller. Opened locally, the pages show their layout
and links, with "Loading..." in place of live values.

---

## Handling differences between sites

Every building is different, and each kind of difference has a place in
`site/`. Use the first row that can express it; rows further down cost more
to maintain.

| The site needs… | Do this | Where |
|---|---|---|
| Fewer displays (no tenants, no dials, …) | Leave their pages out | `pages.yaml` ([`data/pages.yaml`](#datapagesyaml)) |
| Fewer pages of one kind (a level without a page, only some incomers) | List only those; `page: false` on a level | `floors.yaml`, `points.yaml incomers:`, … |
| Different content on a standard page (meters, cards, reports, tabs) | Change the data | `meters.yaml`, `reports.yaml`, `points.yaml`, `site.yaml floor_page:` |
| Different navigation | Edit the menu | `pages.yaml` |
| Different pictures, logos or styles | Add files, or replace engine files of the same name | `site/assets/` |
| Something extra on a standard page (an image, a notice) | An extra | `extras.yaml` ([Extras](#extras-one-off-additions-to-pages)) |
| A display no other site has | A page of its own | `pages.yaml` + `site/templates/<key>.html.j2` |
| Different markup for part of a standard page | A template override (last resort) | `site/templates/` |
| The same thing another site already needed | An engine feature with a default | The template repo |

- **First time, solve it in `site/`.** When a second site needs the same
  thing, make it an engine option or a published component, and use it in an
  example site.
- **Engine changes never break other sites.** New options default to
  today's output (see [Backward compatibility](#backward-compatibility)), and
  each site's goldens confirm it on its next pull.
- **Run `build.py --check` after every change.** It names whatever is
  misspelt, missing, or never shown.

---

## How a build works

```
site/data/                       ─┐
_templates/ (+ site/templates/)  ─┼─ _build/build.py ─→ project/<slug>/   (served at /docs/<slug>/)
_assets/    (+ site/assets/)     ─┘                     project/tenants/  (tenants module only)
```

1. **Configure.** Read `site.yaml`. `slug` names the output folder.
2. **Stage.** Copy the engine's runtime skeleton (`_assets/`: project JS and
   CSS, vendor libraries, generic images) into `project/<slug>/`. Then copy
   `site/assets/` over it, so a site file replaces an engine file of the same
   name.
3. **Write the generated JS blocks.** These sit between `BEGIN`/`END` marker
   comments in the staged copy. `_assets/` itself ships them empty and is
   never modified.

   | Block | File | From |
   |---|---|---|
   | `METER_REGISTRY` | `js/project/2.0/meter-templates.js` | `data/meters.yaml` (or `meters.csv`) |
   | `POINTS` | `meter-templates.js` | `data/points.yaml named:` |
   | `BACNET_CONFIG` | `meter-templates.js` | `site.yaml bacnet:` |
   | `ReportUrls` | `js/project/2.0/reports.js` | `data/reports.yaml urls:` |
   | `REPORT_CARDS` | `reports.js` | `data/reports.yaml placements:`: each report's style, title, subtitle, alt text and library id |
   | `SIDEBAR_HTML` | `js/project/2.0/sidebar-template.js` | `data/pages.yaml` (the `sidebar` module; older sites: `sidebar.yaml`) |

   `live-points.js`'s `OVERRIDE_FILE` line is set from
   `site.yaml optergy_override_display`.
4. **Run the modules** the pages in `pages.yaml` need, in the engine's fixed
   order (see [Modules](#modules)). Each renders pages through the Jinja
   templates. Two modules writing the same file is an error.

**Templates.** Pages render from `_templates/`. A file of the same name in
`site/templates/` replaces the engine's copy for that site. A missing
template variable is an error, not a blank.

**Live values in pages.** The runtime fills these in on load:

- `data-meter-id="<id>" data-meter-field="status|demand|energy|daily|monthly"`:
  the address comes from `METER_REGISTRY` and `BACNET_CONFIG`.
- `data-point="<name>"`: a named point from `POINTS`.
- `data-bacnet="<device>|<object type>|<instance>|85|-1" data-format="<fmt>"`:
  a literal BACnet address, bound directly.

Formats are `energy`, `power`, `number`, `percentage`, `percentage_signed`,
`temperature`, `status`, `nabers`, `voltage`, `current`, `cost`,
`electariff`, `gas`, `water` and `weight`. Live values are polled through the
controller's own `/js/` libraries (cache-busted with `optergy_lib_version`).

**Where pages go.**
- Everything lands flat in `project/<slug>/`. On a
  [campus](#add-a-building-campus), each building's pages go in their own
  folder instead.
- Tenant pages go to `project/tenants/<tenant>/`, alongside the site folder.
- The controller serves `project/` at `/docs/`. So a link written as
  `/docs/<path>` points at `project/<path>`, which is how tenant pages and
  other sites are linked.

### Repository layout

| Path | Contents |
|---|---|
| `_build/build.py` | Engine: configure, data readers, layout derivation, page builders, `MODULES`, `--check`, CLI |
| `_build/build_switchboards.py`, `build_risers.py` | The `switchboards` and `risers` modules |
| `_build/jsblocks.py` | Renders and injects the generated JS blocks |
| `_build/meters_yaml.py` | `meters.yaml` reader and writer |
| `_build/import_meters.py` | Imports a `meters.csv` export into `meters.yaml` |
| `_build/generate_meter_registry.py` | `meters.csv` reader and cell normalisers |
| `_build/linkcheck.py` | `--check`'s checks on built pages |
| `_build/components.py` | Extras: the component catalog, slots, placement checks |
| `_build/regress.py` | Golden regression harness |
| `_templates/` | Engine page templates; shared macros in `partials/macros.j2` |
| `_assets/` | Runtime skeleton copied into every build. Site-neutral |
| `_components/` | The component catalog for [extras](#extras-one-off-additions-to-pages), and `published.yaml`, its compatibility contract |
| `examples/minimal/` | *Acme Depot*: one storey, electricity/solar/gas/water, building performance |
| `examples/campus/` | *Riverside Campus*: two buildings, per-building folders, switchboards with a cross-building bus tie |
| `tests/` | Unit tests, `--check` tests, the golden check, the engine-neutrality check |
| `site/` | **Your building** (not in the template) |

---

## The site directory

```
site/
  data/         one YAML per kind of data, numbered in fill-in order: 00_site.yaml, 01_pages.yaml, 02_floors.yaml, 03_meters.yaml, …
  pages/        HTML fragments: own-page bodies (`pages` module) and `html` extras
  components/   the site's own components for extras (same format as _components/)
  templates/    overrides of _templates/ files, by name
  assets/       images, SVGs and CSS copied over _assets/ (floorplans, logos, …)
  golden/       regression manifests + CHANGELOG (written by regress.py)
```

Both examples are complete, working sites, and most data files open with a
comment block describing their own schema. When in doubt, copy from an
example.

### `data/site.yaml`

Identity, modules, BACnet addressing, utilities and page config: data file
00, filled in first. It is what makes a directory a site directory. An older
site keeps it at the site root (`site/site.yaml`); a site with both is an
error.

| Key | | Meaning |
|---|---|---|
| `slug` | required | Output folder `project/<slug>/`, and the site's name in its goldens |
| `name`, `short_name` | | Building name: page titles, sidebar header, tenant pages |
| `ems_name` | | Suffix for browser-tab titles (`"Ground Floor Overview · <ems_name>"`) |
| `postcode`, `net_internal_area` | | Shown on the `building_performance` page |
| `modules` | | Older sites only: the page families to build, from [Modules](#modules). A site whose `pages.yaml` is the menu builds what that lists, and can't also have `modules:` |
| `bacnet` | required | `{device, power_offset: {<meter type>: <offset>}}`. A meter's demand point is analog value `base + power_offset[type]`, its status is binary value `base`. Every meter type in the meters file needs an offset |
| `utilities` | required | `{<code>: {label, kind}}` in display order. `code`: lowercase, also the CSS class `.meter-<code>`. `kind`: `electric`, `thermal` (heating and cooling) or `other` |
| `buildings` | campus only | `[{key, name}]`. More than one turns on per-building folders |
| `brand` | `sidebar` | Sidebar header: `{href, label, logo_src}` |
| `footer` | `sidebar` | Sidebar footer: `{logo, logo_alt, email}` |
| `optergy_lib_version` | | `?v=` cache-buster on the controller's `/js/` libraries. Match the controller's firmware |
| `optergy_override_display` | | Optergy display file that point overrides post to. Every overridable point must be in it |
| `summary_roles` | | Summary-card catalog: `{<role>: {title, format}}`. A card's live point is `points.yaml floors:` for (level, role) |
| `floor_page` | | Floor page layout, all optional; see below |
| `tenant_page` | | `summary_label` (first tab's label, default `Floorplan`); `tabs`: which `floor_page` tab ids tenant pages show (default all) |

`floor_page` keys:

| Key | Default | Meaning |
|---|---|---|
| `tabs` | none | Report tabs: `[{id, label, slot, roles}]`. Each shows its `roles`' summary cards, then the `reports.yaml` placements for `page: floor, floor: <key>, slot: <slot>` |
| `report_titles` | none | Report-card titles by position within a tab, e.g. `[Demand, Consumption]` |
| `summary_label` | `Summary` | Label of the first (floorplan) tab |
| `summary_cards` | none | Cards beside the floorplan: `{total\|tenants\|landlords: <meter function>}`. Each binds the floor's meter with that `function` |
| `centre_zone` | none | Zone name whose column gets the "top card" style (e.g. a landlord riser) |
| `zone_suffix` | `""` | `{centre, side}`: appended to the centre zone's card title and to the others |
| `zone_subtitles` | by kind | Card subtitle per utility-kind mix: keys `electric`, `thermal`, `electric+thermal`, … Default: `Electricity`, `Heat Energy`, `Electrical & Heat Energy`, else the utility labels |
| `riser_card_link` | `#` | Default link on the zone and riser card headers (`#` = none) |
| `floorplan` | `right` | The floorplan image: `right` (beside the summary cards, hidden on narrow screens), `top` (above them, full width) or `none` |
| `meter_columns` | `3` | Columns of the riser grid: `1`–`4`, or `auto`, as many as the page's cards use (its meters' `column` values, at most 4). Placement stays the meters' `column`: a column past the grid's wraps onto a new row (`--check` warns) |
| `summary_layout` | `split` | `split`: the total card, then tenants and landlords below it; `row`: every summary card in one row. Tenant pages show only the total card |

`floorplan`, `meter_columns` and `summary_layout` are the floor pages' layout. A
level in `floors.yaml` can set any of them for its own pages, its tenant pages
included.

### Data files and the order to fill them in

Fill in `data/` in this order. Each file may carry its number
(`data/02_floors.yaml`) so a directory listing shows the order; the build
finds a file with or without it. Keep only `site.yaml`, `pages.yaml` and the
files the pages you list need, keeping their numbers, so a gap is a file the
site doesn't use. `examples/minimal/data/` has 00–04, 08, 14 and 15.

| # | File | What | Needed by |
|---|---|---|---|
| 00 | [`site.yaml`](#datasiteyaml) | Identity, BACnet addressing, utilities, page config | every site |
| 01 | [`pages.yaml`](#datapagesyaml) | Every page the site builds, laid out as its menu | every site |
| 02 | [`floors.yaml`](#datafloorsyaml) | Levels bottom → top, and the tenant holding each level's cores | every site |
| 03 | [`meters.yaml`](#datametersyaml) or [`meters.csv`](#datameterscsv-the-export-format) | Every meter: by level → core, or the export as it is. One or the other | every site |
| 04 | [`points.yaml`](#datapointsyaml) | Every BMS point the pages show, grouped by page: named points, floor summary cards, the incomer pages, the home page | most sites |
| 05 | [`tenants.yaml`](#datatenantsyaml) | The tenant catalog: proper names, folders, tenant pages | `tenants` |
| 06 | `incomers.yaml` | Older sites: `points.yaml incomers:` | `incomers` |
| 07 | `home.yaml` | Older sites: `points.yaml home:` | `home` |
| 08 | `meters_hierarchy.yaml` | Optional: the meters hierarchy page's texts and root meters | `meters_hierarchy` |
| 09 | `switchboards.yaml` | Switchboard diagrams | `switchboards` |
| 10 | `risers.yaml` | Riser diagrams | `risers` |
| 11 | `schematics.yaml` | SVG schematic pages | `schematics` |
| 12 | `energy_flow.yaml` | The energy-flow Sankey | `energy_flow` |
| 13 | `dials.yaml` | Live gauges | `dials` |
| 14 | `reports.yaml` | Report cards, placed on the pages above | most pages |
| 15 | [`extras.yaml`](#extras-one-off-additions-to-pages) | Components placed on the pages above | any |
| 16 | `sidebar.yaml` | Older sites: the menu, before it moved into `pages.yaml` | `sidebar` |

`meters.csv` is read as it is, so a new export is just dropped in; it may be
numbered too (`03_meters.csv`). `--check` warns about a file in `data/` the
build doesn't read, such as a misspelt name. An older site's root
`site.yaml`, `bms_bindings.yaml`, `incomers.yaml`, `home.yaml`, a slug-keyed
`tenants.yaml`, a `tenants:` block in `floors.yaml`, `sidebar.yaml` and
`site.yaml modules:` keep working.

### `data/pages.yaml`

**Every page the site builds, laid out as the sidebar menu.** The build
makes what it lists, and only that, and generates the menu from it.

```yaml
top_items: []
sections:
  - header: METERING
    items:
      - label: Floors
        icon: bxs-building
        pages: floors                  # every floor page, as this sub-menu
        groups:
          - { label: "Floors 1st - 12th", from: 12th, to: 1st }
      - label: Meters
        icon: bx-tachometer
        children:
          - { label: "Hierarchy tree", page: meters_hierarchy }
          - { label: "Meter Displays", href: "/meters/MeterDisplayManager.html?hideup", target: _blank }
      - label: Services
        icon: bx-podcast
        children:
          - { label: "Landlord Services", page: landlords }   # the site's own page
bottom_items:
  - { label: Logout, icon: bxs-user, href: "/Login.html?logout", class: menu-logout }
unlisted:                              # built, but not in the menu
  - { page: home }
```

Top-level keys: `sections: [{header, items}]`, `top_items`, `bottom_items`,
`unlisted` (page entries that aren't in the menu), and `brand` and `footer`
(default: `site.yaml`'s). Menu items are listed under
[Menu items](#other-data-files). A page entry is one of:

- **`pages: <family>`**: every page of a family: `floors`, `incomers`,
  `switchboards`, `risers`, `tenants`, or `buildings` (a campus: a sub-menu
  per building of its floors, incomers and boards). With a `label:` and
  `icon:` the pages become that sub-menu; without, they're listed in place.
  `only:`, `groups:` and `building:` shape the menu. Which pages a family has
  is up to its own data (`points.yaml incomers:`, `page: false` on a level, …).
- **`page: <key>`**: one page, `<key>.htm`.
  - **Generated pages:** `home`, `meters_hierarchy`, `building_performance`,
    `energy_flow` and `dials`, a schematic, or any floor, incomer or board
    page. Each is built by its module, from its data file.
  - **Any other key is a page of the site's own.** It renders from
    `site/templates/<key>.html.j2` if that exists (extend `base.html.j2`).
    Otherwise it renders from `pages/<key>.body.html` (plus optional
    `.styles.html`, `.extra_scripts.html` and `.tail_scripts.html`). Without
    either, it's an empty page: the header, menu and scripts, to fill in
    later.
  - **Own-page fields:** `heading` (default: the `label`), `page_title`
    (default: `"<heading> · <ems_name>"`), `out`, `container_class`,
    `container_style`, `layout_mode`, `no_optergy: true` (skips the
    controller's `/js/` libraries) and `building`. Fragments and headings can
    use `{{ building.* }}` and `{{ path_prefix }}`.

The modules to run follow from the entries, so this file replaces
`sidebar.yaml` and `site.yaml modules:`. A site with either of them alongside
it is an error. An older site's `pages.yaml` is a
`pages: [{key, out, page_title, heading, …}]` list of frozen pages, which
works as before, beside `sidebar.yaml` and `modules:`.

### `data/floors.yaml`

The **level roster**: one `floor_<key>:` entry per level, **bottom to top**.
File order is the physical order the sidebar, tenant lists and riser
diagrams follow, so keys can be anything (`L00`, `ground`, `Mezz`, `Roof`).
Every floor named anywhere else must be a level here; `--check` enforces it.

| Field | Default | Meaning |
|---|---|---|
| `label` | the key | Display name (tenant pages, floor lists) |
| `nav_label` | `label` | Sidebar text |
| `heading` | `"<label> Overview"` | Floor page heading |
| `page` | `true` | `false` for a level with meters but no page (plant basement, roof) |
| `building` | | Campus: the building the level belongs to (required there). Level keys are unique site-wide |
| `cores` | | `{<core>: <tenant short name>}`: which tenant holds each of the level's cores. A core is a floor-page card: a group of a level's meters in `meters.yaml`, a `zone` in `meters.csv`. In `meters.yaml` its meters take its tenant. A core left out is the landlord's. No page shows cores yet |
| `floorplan`, `meter_columns`, `summary_layout` | `site.yaml floor_page`'s | This level's page layout (see [`floor_page` keys](#datasiteyaml)), e.g. `floorplan: none` for a level with no plan |
| anything else | | Passed to the floor page, e.g. `floorplan_image` (default `img/floors/floor_<key>.png`), `floorplan_tab: {floorplan_after_column, layout}` |

A level with a page gets `floor_<key>.htm`, laid out from its meters:
- cards are grouped by (column, zone) and ordered by position;
- the columns with cards fill the riser grid in order (`floor_page.meter_columns` wide);
- the floorplan sits beside or above the summary cards (`floor_page.floorplan`).

A page level with no meters and no explicit `floorplan_tab.layout` is an
error.

**Cores.** A level's `cores:` names which tenant holds each of its cores (the
floor-page cards the meters file groups a level's meters into: `meters.yaml`'s
groups, `meters.csv`'s `zone`), by short name from
[`tenants.yaml`](#datatenantsyaml). A core left out is the landlord's.

```yaml
floor_L03:
  label: "3rd Floor"
  cores:
    West: Fern & Co
    East: Fern & Co
```

### `data/meters.yaml`

Every meter, laid out the way the building is: **level → core → meter**.
Fill it in after `floors.yaml`, whose levels and cores it uses.

```yaml
columns: {West: 0, North: 1, East: 2}   # floor-page column of each core's card

floor_L03:                  # a level from floors.yaml
  floor:                    # meters outside the cores: floor totals, …
    - {id: 30, tag: Floor 3 Total, base: 20300, type: Calculation, function: Floor Total Electricity, utility: electricity}
  West:                     # a core: the meters on its card, top to bottom
    - {id: 31, tag: DB-03 Lighting, base: 10900, type: Modbus, parent: 1, function: Lighting, utility: electricity}
    - {id: 32, tag: DB-03 Small Power, base: 11000, type: Modbus, parent: 1, function: Small Power, utility: electricity}

unplaced:                   # meters on no level: site totals, gas and water incomers
  - {id: 10, tag: Main Incomer - Gas, base: 11000, type: Modbus, parent: 0, function: Incomer, utility: gas}
```

| Field | Default | Meaning |
|---|---|---|
| `id` | required | Unique integer. What `data-meter-id` and every other meter reference uses |
| `tag` | | Meter name (shown in the hierarchy, switchboard and riser widgets) |
| `base` | required | BACnet instance base: energy is analog value `base`, status is binary value `base` |
| `type` | | Meter type, e.g. `Modbus`, `Calculation`. Picks `bacnet.power_offset` |
| `daily`, `monthly` | `0` | Analog-value instances of the daily / monthly consumption points |
| `parent` | not in the hierarchy | Parent meter's `id`: builds the meters hierarchy and switchboard/riser ways. `0` = a root |
| `function` | | Short in-card label. Special values: summary-card functions named in `floor_page.summary_cards`; `Riser-meter` (the `risers` module) |
| `utility` | | A `site.yaml` utility code or label, any case. Add `-virtual` for a calculated meter (`lthw-virtual`, styled with a faded edge). `Fluid energy` resolves to the thermal code named in `function` |
| `tenant` | the core's tenant | Tenant short name(s) from `tenants.yaml`, comma-separated; `null` for none. A name that isn't a tenant (a landlord area) shows on no tenant page |
| `tenant_display` | `no` | `yes` = shown on tenant pages |
| `main_display` | `yes` | `no` = hidden from the main floor pages |
| `column` | the core's `columns:` entry | A core's meters only: floor-page column |
| `position` | in a core, one after the meter above it (`0` for the first); elsewhere none | Order on the card. Outside the cores it's kept as the export has it |
| `also_on` | | `[<level>, …]`: the meter also shows on these levels' pages, on the same card |

**Tenants follow the cores.** A meter in a core takes the tenant
`floors.yaml` gives that core. A meter in a level's `floor:` group takes the
level's tenant when every core listed on the level is one tenant's. Write
`tenant:` only for the exceptions, e.g. `tenant: null` for a landlord meter
in a tenant's core.

The file is listed level by level for reading; the build orders meters by
`id`. Duplicate ids are an error, and so are two meters sharing a level,
column, core and position.

**Importing an export.** `_build/import_meters.py <export.csv> [--site DIR]`
writes the site's meters YAML from a [`meters.csv`](#datameterscsv-the-export-format)
export, numbered like the site's `floors.yaml` (`03_meters.yaml`). Fill in
`floors.yaml`'s `cores:` first: the import writes `tenant:`, `column:` and
`position:` only where the export differs from the defaults above. It reads
its own output back and writes nothing unless that gives the export's meters
exactly. Re-importing (`--replace`) replaces the whole file, including hand
edits.

### `data/meters.csv`: the export format

A spreadsheet or controller export, one row per meter. A site can build from
it directly, so a new export is just dropped in, or turn it into `meters.yaml`
(above) with `_build/import_meters.py`. Both give the same output; a site
can't have both files. Columns, in order:

| Column | Meaning |
|---|---|
| `id` | Unique integer. What `data-meter-id` and every other meter reference uses |
| `tag` | Meter name (shown in the hierarchy, switchboard and riser widgets) |
| `base` | BACnet instance base: energy is analog value `base`, status is binary value `base` |
| `type` | Meter type, e.g. `Modbus`, `Calculation`. Picks `bacnet.power_offset` |
| `daily`, `monthly` | Analog-value instances of the daily / monthly consumption points (blank = 0) |
| `parent_id` | Parent meter: builds the meters hierarchy and switchboard/riser ways. `0` = a root; blank = not in the hierarchy |
| `floor` | Level key(s) from `floors.yaml`. Several floors separated by `/` (`3rd/4th`) put the meter on each page |
| `column` | Floor-page column (0, 1, …). Blank = not on the floor grid |
| `zone` | The core whose card the meter sits in (cards group by column + zone). Blank = outside the cores |
| `position` | Order within the column |
| `function` | Short in-card label. Special values: summary-card functions named in `floor_page.summary_cards`; `Riser-meter` (the `risers` module) |
| `utility` | A `site.yaml` utility code or label, any case. Add `-virtual` for a calculated meter (`lthw-virtual`, styled with a faded edge). `Fluid energy` resolves to the thermal code named in `function` |
| `tenant` | Tenant short name(s), the `tenants.yaml` keys, comma-separated. A name that isn't a tenant (a landlord area) shows on no tenant page |
| `tenant_display` | `yes` = shown on tenant pages (default no) |
| `main_display` | `no` = hidden from the main floor pages (default yes) |

`n/a` in any cell except `id` and `base` counts as blank. Integer cells are
validated, and duplicate ids are an error. So are two meters sharing a floor,
column, zone and position.

### `data/points.yaml`

**Every BMS point the pages show, grouped by page.** A meter's own points
(demand, status, daily, monthly) come from the meters file; these are the
rest: BMS calculation points and sensors. Addresses are
`"<device>|<object type>|<instance>|85|-1"`.

```yaml
named:                         # any page: data-point="<name>"
  nabers_rating: { bacnet: "300|2|86|85|-1", format: nabers }
floors:                        # floor summary cards: level → summary role
  floor_L00:
    floor_today_electricity: { id: live-l00-elec-today, bacnet: "300|0|2000001|85|-1" }
incomers:                      # the incomer pages, one per key
  incomer_gas:
    heading: "Gas Main Incomer"
    summary_cards:
      - { title: "Monthly Consumption", id: live-gas-monthly, bacnet: "300|0|2000011|85|-1", format: gas }
home:                          # the home page
  heading: "Acme Depot Energy Management System"
  info_bar:
    - { label: "Gas Today", link: incomer_gas.htm, id: live-home-gas-today, bacnet: "300|0|2000011|85|-1", format: gas }
```

| Section | Used by | Contents |
|---|---|---|
| `named` | any page using `data-point` | `{<name>: {bacnet, format}}`: named points (degree days, NABERS rating, …). The build writes them into the runtime's `POINTS` |
| `floors` | `floors`, `tenants` | `{floor_<key>: {<role>: {id, bacnet}}}`: the live point behind each summary card. Roles are `site.yaml summary_roles:`; `id` is the element id. A level with no point for a role shows "N/A" |
| `incomers` | `incomers` | `{<key>: {heading, summary_cards, stat_grids?, reports?, template?, nav_label?, building?}}` → `<key>.htm`. A card is `{title, value}` (static), `{title, meter_id, meter_field}` or `{title, id, bacnet, format}`. `incomer_<utility code>` keys take their menu label from the utility |
| `home` | `home` | `heading`, `page_title`, `info_bar: [{label, link, value \| id+bacnet+format}]`, `welcome_title`, `bullet_points`, `top_reports?`, `reports?`. Report cards: placements `page: home`, slots `top` and `main` |

An older site writes `points:` for `named:` and keeps the other sections in
`bms_bindings.yaml` (`bindings: [{role, floor, id, bacnet}]` rows),
`incomers.yaml` and `home.yaml`. These still work. A section in both places
is an error.

### `data/tenants.yaml`

**The tenant catalog**: `tenants:`, one entry per tenant, keyed by its
**short name**, the spelling a meter's `tenant` uses and the one a level's
`cores:` names. Entry order is the menu's tenant order.

```yaml
tenants:
  Fern & Co:                   # short name
    name: "Fern and Company"   # proper name
    index: {}
```

| Field | Default | Meaning |
|---|---|---|
| `name` | the short name | Proper name: the tenant pages' "Tenant" card, titles and sidebar |
| `slug` | the short name lower-cased, other characters → `-` | Output folder, `project/tenants/<slug>/`. Set it when the default isn't the folder you want |
| `index` | | `{}` (or `{page_title, title, reports}`) adds the tenant's `index.htm` |
| `extra_floors` | | Floors with no meters tagged to the tenant yet that get a page anyway |
| `exclude_floors` | | Floors a tagged meter would add that don't get a page |
| `floors` | | `{<key>: {heading, page_title, floorplan_tab_label, floorplan_image, floorplan_after_column, <slot>_reports}}`: per-floor overrides |

A tenant gets a page for each floor its tagged meters name. Each page shows
that floor's meters tagged with the tenant's short name and
`tenant_display: yes`, plus untagged ones with `tenant_display: yes`. With
any `cores:` set, `--check` adds three checks:
- every core must name a catalog tenant (error);
- a tagged meter must sit in a core of its tenant's. A meter whose zone isn't
  a core, such as a floor total, needs its tenant to hold some core on that
  floor (warning);
- every tenant must hold a core somewhere (warning).

Also read: a `tenants:` block in `floors.yaml` (where the catalog lived before
it had its own file), and an older site's `tenants.yaml` keyed by slug
(`<slug>: {display_name, registry_tenant, …}`). The catalog can't be in two
places.

### Other data files

Each file belongs to the module that reads it. Only the files of the pages
`pages.yaml` lists are needed.

| File | Module | Contents |
|---|---|---|
| `reports.yaml` | most pages | `urls: {<image_ref>: <chart image URL>}` and `placements: [{id, image_ref, alt, page, slot, position, floor?, tenant?, incomer?, title?, subtitle?, kind?}]`: which report cards appear where. `id` is the report-library item the card links to. A page writes each card as one line, `<div data-report="<image_ref>"></div>`, which `reports.js` builds into the card. Its title is the placement's `title`; a floor tab's untitled cards are titled by order (`floor_page.report_titles`). `kind` is its style: `headed`, a header band (home's default); `titled`, a title and `subtitle` (building performance's default); `plain` everywhere else |
| `incomers.yaml`, `home.yaml` | `incomers`, `home` | Older sites: what [`points.yaml incomers:` and `home:`](#datapointsyaml) hold now |
| `meters_hierarchy.yaml` | `meters_hierarchy` | Optional. `page_title`, `heading`, `subtitle`, `search_placeholder`, `root_meter_ids: [ … ]` (one tree per root). Without it the page has default texts, and its trees start at the meters marked `parent: 0`, and at those with no parent that feed another |
| `sidebar.yaml` | `sidebar` | Older sites: the menu, `top_items`, `sections: [{header, items}]`, `bottom_items`; see below, with `auto: <family>` where `pages.yaml` writes `pages: <family>` |
| `pages.yaml` (older sites) | `pages` | Frozen pages: `pages: [{key, out, page_title, heading, building?}]`, plus optional shell settings `container_class`, `container_style`, `layout_mode` and `no_optergy: true` (skips the controller's `/js/` libraries). Body from `pages/<key>.body.html`, plus optional `<key>.styles.html`, `.extra_scripts.html`, `.tail_scripts.html` |
| `switchboards.yaml` | `switchboards` | `defaults: {default_rating, layout}`, `boards: {<key>: {incomer_id, heading, ways: {<meter id>: {rating, ct}}, bus_tie?, nav_label?, building?}}`. A board's ways are every meter whose `parent` is its `incomer_id` |
| `risers.yaml` | `risers` | `defaults: {default_rating, floors_per_page, layout}`, `overrides: {<meter id>: {floors_per_page?, layout?, nav_label?}}`. Risers are the meters with `function: Riser-meter`; their floor taps are their child meters. A riser past `floors_per_page` floors splits into linked pages `riser_<id>_p1`, `_p2`, … |
| `bms_bindings.yaml` (older sites) | `floors`, `tenants` | Now `points.yaml floors:` |
| `energy_flow.yaml` | `energy_flow` | Live Sankey: `nodes`, `floors: [{key, node}]`, `floor_end_uses`, `landlord_flows`, optional `gas` + `heat_flows`. Its topology (Electricity → Tenants/Landlord, Gas → Boilers) is fixed in `build_energy_flow` |
| `dials.yaml` | `dials` | `dials: [{bacnet, label, format, min, max, …}]`: live segmented gauges |
| `extras.yaml` | any | `extras: [{component, pages, slot, <options>}]`: components added to pages; see [Extras](#extras-one-off-additions-to-pages) |
| `schematics.yaml` | `schematics` | `<key>: {heading, background, overlays: [{kind: link\|meter\|status\|raw, position, …}]}`: SVG pages with positioned live widgets |

**Menu items** (`pages.yaml`, or an older site's `sidebar.yaml`). Each item is one of:

| Item | Meaning |
|---|---|
| `{label, page: <key>, icon?, target?, rel?, class?}` | A page the site builds (`pages.yaml` only; see [`data/pages.yaml`](#datapagesyaml)) |
| `{label, href, icon?, target?, rel?, class?}` | An outside link |
| `{label, icon, children: [ … ]}` | A sub-menu |
| `{pages: <family>}`, or `{label, icon, pages: <family>}` as a sub-menu | `pages.yaml`'s family entry: builds the family's pages and lists them as `auto:` does |
| `{auto: floors \| incomers \| switchboards \| risers \| tenants \| buildings}` | `sidebar.yaml` only: a list derived from the data. `floors` lists the page levels, top first. `risers` links each riser's first page, labelled with its tag (or `nav_label`). `buildings` makes one sub-menu per building with its floors, incomers and boards |
| `… only: [keys]` | Picks and orders a derived list |
| `… groups: [{label, from, to}]` | Splits a derived list into range sub-menus |
| `… building: <key>` | Limits a derived list to one building |
| `{kind: theme_toggle}` | The light/dark switch |

Hrefs are written relative to the site root; the build rewrites them for each
campus folder.

---

## Modules

A module runs when `pages.yaml` lists its pages (an older site lists modules
in `site.yaml modules:`). Modules always run in this order:

| Module | Writes | Reads |
|---|---|---|
| `floors` | `floor_<key>.htm` per page level | `floors.yaml`, the meters file, `points.yaml floors:`, `reports.yaml` |
| `incomers` | `<key>.htm` per incomer | `points.yaml incomers:`, `reports.yaml` (page `incomer`, slot `main`) |
| `home` | `home.htm` | `points.yaml home:`, `reports.yaml` (page `home`, slots `top` and `main`) |
| `meters_hierarchy` | `meters_hierarchy.htm` | the meters file; `meters_hierarchy.yaml` if it has one |
| `schematics` | `<key>.htm` per schematic | `schematics.yaml` |
| `building_performance` | `building_performance.htm` | `points.yaml named:`, `reports.yaml` (page `building_performance`, slots `pie` and `right`) |
| `pages` | `<out>` per page of the site's own | `pages.yaml`, `site/templates/<key>.html.j2` or `pages/` |
| `tenants` | `../tenants/<slug>/{index,floor_<key>}.htm` + a sidebar per tenant | `tenants.yaml`, `floors.yaml`, the meters file, `points.yaml floors:`, `reports.yaml` |
| `energy_flow` | `energy_flow.htm` | `energy_flow.yaml` |
| `dials` | `dials.htm` | `dials.yaml` |
| `switchboards` | `<key>.htm` + `img/<key>.svg` per board | `switchboards.yaml`, the meters file |
| `risers` | `riser_<id>[_pN].htm` + SVGs | `risers.yaml`, the meters file |
| `sidebar` | the `SIDEBAR_HTML` block (+ one sidebar per campus building folder) | `pages.yaml` (older sites: `sidebar.yaml`) |

"The meters file" is `meters.yaml` or `meters.csv`. Every page's report
cards come from `reports.yaml`; the build writes them into `reports.js`
(`REPORT_CARDS`), which draws each `<div data-report="…">` on load.

`building_performance` uses seven named points: `hdd_15_5`, `cdd_15_5`,
`occupancy_above_20`, `annual_electricity`, `annual_gas`, `energy_intensity`
and `nabers_rating`.

---

## Extras: one-off additions to pages

When a site needs something on a standard page that the engine doesn't draw,
such as an extra image or a notice, it places a **component** in a **slot**.
No template override is needed:

```yaml
# site/data/15_extras.yaml
extras:
  - component: image          # from the catalog below, or the site's own components/
    pages: [floor_3rd]        # page keys and/or page kinds (floor, incomer, home)
    slot: after_summary       # where on those pages
    src: img/plant_room.png   # the component's options
    caption: "Plant room"
```

- **Page keys** are `floor_<level>`, a `points.yaml incomers:` key, or `home`. A
  kind means every page of that kind.
- **Several extras in one slot** render in file order. A slot with nothing in
  it renders nothing.
- **`--check` validates every placement:** the component, pages, slot and
  options. It also warns when a placement never appears, because its module
  is off or the page uses a site template override without that slot.

**Slots**

| Page | Slots, top to bottom |
|---|---|
| floor | `top` (above the tabs), `after_summary` (below the floorplan and summary cards), `after_risers` (end of the floorplan tab), `bottom` (below all tabs) |
| incomer | `top`, `after_cards` (below the summary cards), `bottom` |
| home | `top`, `after_info_bar`, `bottom` |

**The catalog**

| Component | Options (required in bold) | What it is |
|---|---|---|
| `image` | **`src`**, `alt`, `caption`, `width` (default `100%`) | An image with an optional caption. A relative `src` is from the site root |
| `html` | **`file`** | Any HTML: a fragment file in `site/pages/` that can use `{{ building.* }}` and `{{ path_prefix }}`. The catch-all for one-offs |
| `live_value` | **`title`**; exactly one of `meter_id` (+ `meter_field`: `demand`, `energy`, `daily`, `monthly`, `status`), `point` or `bacnet`; `format`, `decimal_places`, `refresh`, `id` | A card with a title and one live value, styled like the incomer summary cards. `format` defaults to the meter field's or the point's own, or `number` for a raw address |

Each component's `component.yaml` documents its options.

**Handling a one-off:**
1. **An existing component fits:** place it.
2. **Something new:** use `html` with a fragment. It works straight away.
3. **It comes up again, or needs options:** make it a component in
   `site/components/<name>/`. A site component with an engine component's
   name replaces it for that site. It's two files:
   - `component.yaml` declares a `description` and its options. Each option
     is `required: true` or has a `default:`, and can list the `choices:` it
     accepts. `one_of: [[a, b, …]]` makes a placement give exactly one of a
     group.
   - `component.html.j2` renders it. It sees its options plus `path_prefix`,
     `page_kind`, `page_key`, `building`, and `extra_id`: a DOM id that's
     unique on the page.
4. **A second site wants it:** move it into the template's `_components/`,
   publish it (see [Backward compatibility](#backward-compatibility)), and
   place it in an example.

---

## How to…

### Add a level
Add `floor_<key>:` to `floors.yaml` in its physical position, and list its
meters under `floor_<key>:` in `meters.yaml` (or give them `floor` `<key>` in
`meters.csv`). Use `page: false` for a level with meters but no page. If the
level has a page, add a floorplan at `site/assets/img/floors/floor_<key>.png`.

### Add a meter
Add it to `meters.yaml` with a new `id`, under its level.
- **On a floor page:** put it in its core's list, where it should appear on
  the card, and give it a `function` and `utility`.
- **Outside the cores** (a floor total): put it in the level's `floor:` list.
- **In the hierarchy or a switchboard:** give it a `parent`.

A site built from `meters.csv` adds a row instead, or takes a new export:
`floor`, `column`, `zone` and `position` place it, `parent_id` links it. A
new meter `type` needs a `bacnet.power_offset` entry.

### Add a utility
Add `<code>: {label, kind}` to `site.yaml utilities:`, use the code (or its
label) as a meter's `utility`, and add a `.meter-<code>` CSS rule
(`--check` warns when one is missing). Zone headers take their colour from
that class. For an incomer page, add `incomer_<code>` to `points.yaml incomers:`.

### Add a kind of page
List its pages in `pages.yaml` (`page: <key>` or `pages: <family>`) and
create its data file, numbered as in the [table](#data-files-and-the-order-to-fill-them-in),
starting from an example's. An older site adds the module to
`site.yaml modules:` instead. Then run `--check`. If the module draws from
meters (`switchboards`, `risers`), the meters need the right `parent` or
`function`.

### Add a building (campus)
1. List each building in `site.yaml buildings:`.
2. Give every level a `building:`.
3. Optionally, give incomers, boards and the site's own pages a `building:`.

That building's pages then go to `project/<slug>/<building>/`, each folder
gets its own sidebar, and `pages: buildings` builds a sub-menu per building.
Frozen fragments in a building folder must write relative URLs as
`{{ path_prefix }}img/…`, and `--check` warns when one doesn't. See
`examples/campus`.

### Add a one-off page
Add `{label: "…", page: <key>}` to the menu in `pages.yaml` (or under
`unlisted:`) and build. It's an empty page with the header, menu and scripts
until you add `site/templates/<key>.html.j2` (extending `base.html.j2`) or
`pages/<key>.body.html`.

### Add a live value
- **A meter reading:** `data-meter-id` + `data-meter-field`.
- **A named BMS point:** define it in `points.yaml named:` and use
  `data-point="<name>"`.
- **A floor summary card:** add a `summary_roles` role, list it in a
  `floor_page` tab's `roles`, and give each level its point in `points.yaml floors:`.

### Add a report card
Add the chart URL to `reports.yaml urls:` and a `placements:` row naming the
page, slot and position.

In a site template or an `html` extra, write the card as
`<div data-report="<image_ref>"></div>`. It takes its title, alt text and
library link from the report's placement; a report with only a URL gets a
card with no title that links to `#`.

### Change a page's markup for one site
To **add** something to a standard page, use an
[extra](#extras-one-off-additions-to-pages). To **change** what the page
already draws, copy the template from `_templates/` to `site/templates/`
under the same name and edit it. `--check` lists the overrides in use. Keep
them few: an overridden template no longer picks up engine fixes, and it has
no slots unless you keep them.

---

## Checking a site: `--check`

`build.py --check` never writes to `--out`. It runs two stages.

**1. Data checks.** Each failure is an error:
- floors named anywhere must be levels in `floors.yaml`;
- every meter utility must be in the `utilities` catalog;
- every report `image_ref` must have a URL;
- every point must have an address;
- every page level must have something to draw;
- every `building:` must be a known building.

**2. Trial build.** If the data checks pass, `--check` builds the site's
modules into a temp directory and checks what got rendered:
- **Errors:** the build itself failing, or a `data-point`, meter id or
  `data-report` on a page that names nothing.
- **Warnings:** any file a page links to that the build doesn't produce. This
  covers page and sidebar links, images, scripts, stylesheets and CSS
  `url()`s. Missing files are grouped by folder, which catches links to
  pages nobody builds and assets you haven't added yet. `/docs/<other site>/`
  links can't be checked, so they always show here. Also a warning: a page
  whose markup needs a runtime script it doesn't load, e.g. a `data-meter-id`
  on a page without `meter-templates.js`, whose value would never show.
  A site template override that drops a script line causes it.

Other warnings: a file in `data/` the build doesn't read; a report given
different fields in two places (pages show the first); a utility with no
`.meter-<code>` CSS rule; a `points.yaml floors:` role no page shows; a campus
fragment URL missing `{{ path_prefix }}`.

---

## Regression testing

Each site has **goldens** in its `golden/` directory: sha256 manifests of
every file in its build output. `regress.py` builds each site in a throwaway
copy of the repo and compares. A changed, added or removed file fails the
check, and `regress.py` prints a readable diff when a local copy of the last
golden build exists (`_baseline/`, gitignored).

- **Sites:** `site/` and every `examples/<name>/`; limit a run with `--site DIR`.
- **Variants:**
  - `site`: the pages the site's `pages.yaml` lists (an older site: its
    `modules:`), which is what gets deployed;
  - `extra` (optional): every module except `pages`, to keep the modules a
    site doesn't use from rotting.
- **`check`** must pass before every commit. `pytest` runs it too.
- **`snapshot`** builds twice with different hash seeds, fails if the two
  builds differ, then writes the manifests. Overwriting an existing golden
  needs `--accept "reason"`. The reason is appended to `golden/CHANGELOG`
  with the counts of changed, added and removed files.

The discipline that keeps this useful:
- Treat any output change as a re-baseline, and make it **the only change
  in its step**.
- Decide beforehand what will prove the change is intended. For example,
  "identical once comments are stripped", or "only these files changed".
- Check that proof before accepting.
- Refactors must leave every golden identical.

**What a change looks like.** For a CSS or markup change, a golden only says
that files changed. `_build/stylediff.py OLD NEW` says whether the pages look
the same: build the site with the engine before and after the change
(`build.py --out OLD`, `--out NEW`, both folders side by side), and it opens
every page of both in headless Chromium at 480, 1024 and 1920 px, in light
and dark, and compares each element's computed style, its `::before` and
`::after`, and its box. It needs Chromium (or Chrome) on the `PATH`, and it
can't see `:hover` and `:focus` styles.

---

## Backward compatibility

An older site must keep building, with the same output, on a newer engine.
Every engine change follows these rules:

- **New settings are optional.** A new `site.yaml` key, data field,
  component option or module defaults to today's behaviour, so a site that
  doesn't set it builds byte-identically. The example sites stand in for
  older sites, and their goldens prove it.
- **The extras API only grows.** `_components/published.yaml` lists every
  slot, component and option that sites may use. `tests/test_components.py`
  fails if:
  - any of them is removed or renamed;
  - a component's required options or `one_of` groups change;
  - an option's `choices` shrink;
  - something new isn't published.

  To rename an option, add `aliases: {<old>: <new>}` to its `component.yaml`.
  To remove one, add `retired: [<old>]`. Old placements keep working, and
  `--check` tells the site about the change.
- **Output changes are announced.** Changing a component's markup, a default
  or a template changes the output of every site using it. Those sites'
  goldens show it on their next pull, so make it a deliberate re-baseline
  with a release note.

---

## Upgrading a site from the template

A site repo carries the engine (`_build/`, `_templates/`, `_components/`,
`_assets/`, `examples/`, `tests/`) alongside its own `site/`. Engine changes are made in
the template and pulled into each site. The template never touches `site/`,
so pulls don't conflict with site data.

A site cloned from the template (see
[Starting a new building](#starting-a-new-building)) already shares its
history and has the `template` remote.

A site whose history doesn't share the template's, such as one that existed
before the template was split off, needs a one-time link. This marks the
template's history as merged without changing any files:

```bash
git remote add template <template repo URL>
git fetch template
git merge --allow-unrelated-histories -s ours template/main
```

Each upgrade:

```bash
git pull template main
.venv/bin/python _build/regress.py check     # did the site's output change?
.venv/bin/python _build/build.py --check
```

- **If the goldens still match,** commit.
- **If they changed,** read the diff. A deliberate engine change (one the
  template's release notes call out) is accepted with
  `regress.py snapshot --site site --accept "template <version>: <what changed>"`.
  Anything else is a bug to report upstream.
- **If the site overrides a template the upgrade changed,** compare your
  `site/templates/` copy with the new engine version.

Keep engine fixes in the template, not in a site repo. A fix made only in a
site is lost, or conflicts, at the next pull.
