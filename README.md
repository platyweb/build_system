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
- [The site directory](#the-site-directory): [`site.yaml`](#siteyaml), [`meters.csv`](#datameterscsv), [`floors.yaml`](#datafloorsyaml), [other data files](#other-data-files)
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
3. Edit `site/site.yaml`: `slug`, `name`, `bacnet`, `utilities`, `modules`.
   Then edit `site/data/floors.yaml`, `site/data/meters.csv` and the data
   files of the modules you enable.
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
| Fewer displays (no tenants, no dials, …) | Leave the module out | `site.yaml modules:` ([Modules](#modules)) |
| Fewer pages of one kind (a level without a page, only some incomers) | List only those; `page: false` on a level | `floors.yaml`, `incomers.yaml`, … |
| Different content on a standard page (meters, cards, reports, tabs) | Change the data | `meters.csv`, `reports.yaml`, `bms_bindings.yaml`, `site.yaml floor_page:` |
| Different navigation | Edit the sidebar | `sidebar.yaml` |
| Different pictures, logos or styles | Add files, or replace engine files of the same name | `site/assets/` |
| Something extra on a standard page (an image, a notice) | An extra | `extras.yaml` ([Extras](#extras-one-off-additions-to-pages)) |
| A display no other site has | A frozen page | `pages.yaml` + `site/pages/` |
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
site/site.yaml + site/data/      ─┐
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
   | `METER_REGISTRY` | `js/project/2.0/meter-templates.js` | `data/meters.csv` |
   | `POINTS` | `meter-templates.js` | `data/points.yaml` |
   | `BACNET_CONFIG` | `meter-templates.js` | `site.yaml bacnet:` |
   | `ReportUrls` | `js/project/2.0/reports.js` | `data/reports.yaml urls:` |
   | `SIDEBAR_HTML` | `js/project/2.0/sidebar-template.js` | `data/sidebar.yaml` (the `sidebar` module) |

   `live-points.js`'s `OVERRIDE_FILE` line is set from
   `site.yaml optergy_override_display`.
4. **Run the modules** listed in `site.yaml modules:`, in the engine's fixed
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
  site.yaml     identity, modules, BACnet addressing, utilities, page config
  data/         meters.csv, floors.yaml, one YAML per module (only those the site uses), extras.yaml
  pages/        HTML fragments: frozen pages (`pages` module) and `html` extras
  components/   the site's own components for extras (same format as _components/)
  templates/    overrides of _templates/ files, by name
  assets/       images, SVGs and CSS copied over _assets/ (floorplans, logos, …)
  golden/       regression manifests + CHANGELOG (written by regress.py)
```

Both examples are complete, working sites, and most data files open with a
comment block describing their own schema. When in doubt, copy from an
example.

### `site.yaml`

| Key | | Meaning |
|---|---|---|
| `slug` | required | Output folder `project/<slug>/`, and the site's name in its goldens |
| `name`, `short_name` | | Building name: page titles, sidebar header, tenant pages |
| `ems_name` | | Suffix for browser-tab titles (`"Ground Floor Overview · <ems_name>"`) |
| `postcode`, `net_internal_area` | | Shown on the `building_performance` page |
| `modules` | required | Page families to build, from [Modules](#modules) |
| `bacnet` | required | `{device, power_offset: {<meters.csv type>: <offset>}}`. A meter's demand point is analog value `base + power_offset[type]`, its status is binary value `base`. Every meter type in `meters.csv` needs an offset |
| `utilities` | required | `{<code>: {label, kind}}` in display order. `code`: lowercase, also the CSS class `.meter-<code>`. `kind`: `electric`, `thermal` (heating and cooling) or `other` |
| `buildings` | campus only | `[{key, name}]`. More than one turns on per-building folders |
| `brand` | `sidebar` | Sidebar header: `{href, label, logo_src}` |
| `footer` | `sidebar` | Sidebar footer: `{logo, logo_alt, email}` |
| `optergy_lib_version` | | `?v=` cache-buster on the controller's `/js/` libraries. Match the controller's firmware |
| `optergy_override_display` | | Optergy display file that point overrides post to. Every overridable point must be in it |
| `summary_roles` | | Summary-card catalog: `{<role>: {title, format}}`. A card's live point is the `bms_bindings.yaml` row for (role, floor) |
| `floor_page` | | Floor page layout, all optional; see below |
| `tenant_page` | | `summary_label` (first tab's label, default `Floorplan`); `tabs`: which `floor_page` tab ids tenant pages show (default all) |

`floor_page` keys:

| Key | Default | Meaning |
|---|---|---|
| `tabs` | none | Report tabs: `[{id, label, slot, roles}]`. Each shows its `roles`' summary cards, then the `reports.yaml` placements for `page: floor, floor: <key>, slot: <slot>` |
| `report_titles` | none | Report-card titles by position within a tab, e.g. `[Demand, Consumption]` |
| `summary_label` | `Summary` | Label of the first (floorplan) tab |
| `summary_cards` | none | Cards beside the floorplan: `{total\|tenants\|landlords: <meters.csv function>}`. Each binds the floor's meter with that `function` |
| `centre_zone` | none | Zone name whose column gets the "top card" style (e.g. a landlord riser) |
| `zone_suffix` | `""` | `{centre, side}`: appended to the centre zone's card title and to the others |
| `zone_subtitles` | by kind | Card subtitle per utility-kind mix: keys `electric`, `thermal`, `electric+thermal`, … Default: `Electricity`, `Heat Energy`, `Electrical & Heat Energy`, else the utility labels |
| `riser_card_link` | `#` | Default link on the zone and riser card headers (`#` = none) |

### `data/meters.csv`

The meter source of truth: one row per meter. Columns, in order:

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
| `zone` | Floor card the meter sits in (cards group by column + zone) |
| `position` | Order within the column |
| `function` | Short in-card label. Special values: summary-card functions named in `floor_page.summary_cards`; `Riser-meter` (the `risers` module) |
| `utility` | A `site.yaml` utility code or label, any case. Add `-virtual` for a calculated meter (`lthw-virtual`, styled with a faded edge). `Fluid energy` resolves to the thermal code named in `function` |
| `tenant` | Tenant name(s) as the `tenants.yaml` `registry_tenant` spells them, comma-separated |
| `tenant_display` | `yes` = shown on tenant pages (default no) |
| `main_display` | `no` = hidden from the main floor pages (default yes) |

`n/a` in any cell except `id` and `base` counts as blank. Integer cells are
validated, and duplicate ids are an error. So are two meters sharing a floor,
column, zone and position.

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
| anything else | | Passed to the floor page, e.g. `floorplan_image` (default `img/floors/floor_<key>.png`), `floorplan_tab: {floorplan_after_column, layout}` |

A level with a page gets `floor_<key>.htm`, laid out from its meters:
- cards are grouped by (column, zone) and ordered by position;
- the floorplan sits after column 0.

A page level with no meters and no explicit `floorplan_tab.layout` is an
error.

### Other data files

Each file belongs to the module that reads it. Only the enabled modules'
files are needed.

| File | Module | Contents |
|---|---|---|
| `points.yaml` | any page using `data-point` | `points: {<name>: {bacnet, format}}`: named non-meter points (degree days, NABERS rating, …) |
| `bms_bindings.yaml` | `floors`, `tenants` | `bindings: [{role, floor, id, bacnet}]`: the live point behind each summary card, by (`summary_roles` role, level) |
| `reports.yaml` | most pages | `urls: {<image_ref>: <chart image URL>}` and `placements: [{id, image_ref, alt, page, slot, position, floor?, tenant?, incomer?, title?, subtitle?, kind?}]`: which report cards appear where. `id` is the report-library item the card links to |
| `incomers.yaml` | `incomers` | `<key>: {heading, summary_cards, stat_grids?, reports?, template?, nav_label?, building?}` → `<key>.htm`. A card is `{title, value}` (static), `{title, meter_id, meter_field}` or `{title, id, bacnet, format}`. `incomer_<utility code>` keys take their sidebar label from the utility |
| `home.yaml` | `home` | `heading`, `page_title`, `info_bar: [{label, link, value \| id+bacnet+format}]`, `welcome_title`, `bullet_points`. Report cards: placements `page: home`, slots `top` and `main` |
| `meters_hierarchy.yaml` | `meters_hierarchy` | `heading`, `subtitle`, `search_placeholder`, `root_meter_ids: [ … ]` (one tree per root) |
| `sidebar.yaml` | `sidebar` | `top_items`, `sections: [{header, items}]`, `bottom_items`; see below |
| `pages.yaml` | `pages` | `pages: [{key, out, page_title, heading, building?}]`, plus optional shell settings `container_class`, `container_style`, `layout_mode` and `no_optergy: true` (skips the controller's `/js/` libraries). Body from `pages/<key>.body.html`, plus optional `<key>.styles.html`, `.extra_scripts.html`, `.tail_scripts.html` |
| `switchboards.yaml` | `switchboards` | `defaults: {default_rating, layout}`, `boards: {<key>: {incomer_id, heading, ways: {<meter id>: {rating, ct}}, bus_tie?, nav_label?, building?}}`. A board's ways are every meter whose `parent_id` is its `incomer_id` |
| `risers.yaml` | `risers` | `defaults: {default_rating, floors_per_page, layout}`, `overrides: {<meter id>: …}`. Risers are the meters with `function: Riser-meter`; their floor taps are their child meters |
| `tenants.yaml` | `tenants` | `<slug>: {display_name, registry_tenant, index?, extra_floors?, exclude_floors?, floors?}`. Pages go to `project/tenants/<slug>/`; see the file's header |
| `energy_flow.yaml` | `energy_flow` | Live Sankey: `nodes`, `floors: [{key, node}]`, `floor_end_uses`, `landlord_flows`, optional `gas` + `heat_flows`. Its topology (Electricity → Tenants/Landlord, Gas → Boilers) is fixed in `build_energy_flow` |
| `dials.yaml` | `dials` | `dials: [{bacnet, label, format, min, max, …}]`: live segmented gauges |
| `extras.yaml` | any | `extras: [{component, pages, slot, <options>}]`: components added to pages; see [Extras](#extras-one-off-additions-to-pages) |
| `schematics.yaml` | `schematics` | `<key>: {heading, background, overlays: [{kind: link\|meter\|status\|raw, position, …}]}`: SVG pages with positioned live widgets |

**Sidebar items.** Each item is one of:

| Item | Meaning |
|---|---|
| `{label, href, icon?, target?, rel?, class?}` | A link |
| `{label, icon, children: [ … ]}` | A sub-menu |
| `{auto: floors \| incomers \| switchboards \| tenants \| buildings}` | A list derived from the data. `floors` lists the page levels, top first. `buildings` makes one sub-menu per building with its floors, incomers and boards |
| `… only: [keys]` | Picks and orders a derived list |
| `… groups: [{label, from, to}]` | Splits a derived list into range sub-menus |
| `… building: <key>` | Limits a derived list to one building |
| `{kind: theme_toggle}` | The light/dark switch |

Hrefs are written relative to the site root; the build rewrites them for each
campus folder.

---

## Modules

Enable a module by listing it in `site.yaml modules:`. Modules always run in
this order:

| Module | Writes | Reads |
|---|---|---|
| `floors` | `floor_<key>.htm` per page level | `floors.yaml`, `meters.csv`, `bms_bindings.yaml`, `reports.yaml` |
| `incomers` | `<key>.htm` per incomer | `incomers.yaml` |
| `home` | `home.htm` | `home.yaml` |
| `meters_hierarchy` | `meters_hierarchy.htm` | `meters_hierarchy.yaml`, `meters.csv` |
| `schematics` | `<key>.htm` per schematic | `schematics.yaml` |
| `building_performance` | `building_performance.htm` | `points.yaml`, `reports.yaml` (page `building_performance`, slots `pie` and `right`) |
| `pages` | `<out>` per frozen page | `pages.yaml`, `pages/` |
| `tenants` | `../tenants/<slug>/{index,floor_<key>}.htm` + a sidebar per tenant | `tenants.yaml`, `meters.csv` |
| `energy_flow` | `energy_flow.htm` | `energy_flow.yaml` |
| `dials` | `dials.htm` | `dials.yaml` |
| `switchboards` | `<key>.htm` + `img/<key>.svg` per board | `switchboards.yaml`, `meters.csv` |
| `risers` | `riser_<id>[_pN].htm` + SVGs | `risers.yaml`, `meters.csv` |
| `sidebar` | the `SIDEBAR_HTML` block (+ one sidebar per campus building folder) | `sidebar.yaml` |

`building_performance` uses seven named points: `hdd_15_5`, `cdd_15_5`,
`occupancy_above_20`, `annual_electricity`, `annual_gas`, `energy_intensity`
and `nabers_rating`.

---

## Extras: one-off additions to pages

When a site needs something on a standard page that the engine doesn't draw,
such as an extra image or a notice, it places a **component** in a **slot**.
No template override is needed:

```yaml
# site/data/extras.yaml
extras:
  - component: image          # from the catalog below, or the site's own components/
    pages: [floor_3rd]        # page keys and/or page kinds (floor, incomer, home)
    slot: after_summary       # where on those pages
    src: img/plant_room.png   # the component's options
    caption: "Plant room"
```

- **Page keys** are `floor_<level>`, an `incomers.yaml` key, or `home`. A
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
Add `floor_<key>:` to `floors.yaml` in its physical position, and give its
meters `floor: <key>` in `meters.csv`. Use `page: false` for a level with
meters but no page. If the level has a page, add a floorplan at
`site/assets/img/floors/floor_<key>.png`.

### Add a meter
Add a row to `meters.csv` with a new `id`.
- **On a floor page:** give it `floor`, `column`, `zone`, `position`,
  `function` and `utility`.
- **In the hierarchy or a switchboard:** give it a `parent_id`.

A new meter `type` needs a `bacnet.power_offset` entry.

### Add a utility
Add `<code>: {label, kind}` to `site.yaml utilities:`, use the code (or its
label) in `meters.csv`'s `utility` column, and add a `.meter-<code>` CSS rule
(`--check` warns when one is missing). Zone headers take their colour from
that class. For an incomer page, add `incomer_<code>` to `incomers.yaml`.

### Enable a module
Add it to `site.yaml modules:` and create its data file, starting from an
example's or from the table above. Then run `--check`. If the module draws
from meters (`switchboards`, `risers`), the meters need the right `parent_id`
or `function`.

### Add a building (campus)
1. List each building in `site.yaml buildings:`.
2. Give every level a `building:`.
3. Optionally, give incomers, boards and `pages.yaml` entries a `building:`.

That building's pages then go to `project/<slug>/<building>/`, each folder
gets its own sidebar, and `auto: buildings` builds a sub-menu per building.
Frozen fragments in a building folder must write relative URLs as
`{{ path_prefix }}img/…`, and `--check` warns when one doesn't. See
`examples/campus`.

### Add a one-off page
Add `{key, out, page_title, heading}` to `pages.yaml` and write
`pages/<key>.body.html`. Fragments can use `{{ building.* }}` and
`{{ path_prefix }}`. Link the page from `sidebar.yaml`.

### Add a live value
- **A meter reading:** `data-meter-id` + `data-meter-field`.
- **A named BMS point:** define it in `points.yaml` and use
  `data-point="<name>"`.
- **A floor summary card:** add a `summary_roles` role, list it in a
  `floor_page` tab's `roles`, and bind it per floor in `bms_bindings.yaml`.

### Add a report card
Add the chart URL to `reports.yaml urls:` and a `placements:` row naming the
page, slot and position.

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
- **Errors:** the build itself failing, or a `data-point` / meter id on a
  page that names nothing.
- **Warnings:** any file a page links to that the build doesn't produce. This
  covers page and sidebar links, images, scripts, stylesheets and CSS
  `url()`s. Missing files are grouped by folder, which catches links to
  pages nobody builds and assets you haven't added yet. `/docs/<other site>/`
  links can't be checked, so they always show here.

Other warnings: a utility with no `.meter-<code>` CSS rule; a
`bms_bindings.yaml` role no page shows; a campus fragment URL missing
`{{ path_prefix }}`.

---

## Regression testing

Each site has **goldens** in its `golden/` directory: sha256 manifests of
every file in its build output. `regress.py` builds each site in a throwaway
copy of the repo and compares. A changed, added or removed file fails the
check, and `regress.py` prints a readable diff when a local copy of the last
golden build exists (`_baseline/`, gitignored).

- **Sites:** `site/` and every `examples/<name>/`; limit a run with `--site DIR`.
- **Variants:**
  - `site`: the site's own `modules:`, which is what gets deployed;
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
