// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.

// ─── Meter Template System ────────────────────────────────────────────────────
// Auto-generates live point attributes (id, data-bacnet, data-format) from
// a central meter registry. In HTML, simply use:
//
//   <div data-meter-id="1" data-meter-field="status"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="demand"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="energy"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="daily"   data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="monthly" data-refresh="10">Loading...</div>
//
// ─── Updating the registry ───────────────────────────────────────────────────
//   Edit site/data/meters.csv and rebuild (python _build/build.py) — the build
//   regenerates the METER_REGISTRY block below from the CSV. Every block
//   between GENERATED/POINTS markers in this file is written by the build;
//   edits made here are overwritten.
//
// ─── ID Convention ───────────────────────────────────────────────────────────
//   id = "live-{slug}-{field}"
//   where {slug} is the tag column slugified (lowercase, spaces/special → hyphens)
//   and {field} is: status | demand | energy | daily | monthly
//
// ─── BACnet Address Rules ────────────────────────────────────────────────────
//   status:  {device}|3|{base}|85|-1                → data-format="status"
//   energy:  {device}|0|{base}|85|-1                → data-format="energy"
//   demand:  {device}|0|{base + powerOffset}|85|-1  → data-format="power"
//            powerOffset = BACNET_CONFIG.powerOffset[meter type]
//   daily:   {device}|0|{daily}|85|-1               → data-format="energy"
//   monthly: {device}|0|{monthly}|85|-1             → data-format="energy"
//   device and the power offsets come from BACNET_CONFIG below.
//
// ─── Placement fields (optional, used by the static page generator) ──────────
//   Meters that appear on a floor or tenant page carry extra fields that
//   the Python build (build.py + floor.html.j2 / tenant_floor.html.j2)
//   groups by to derive the layout (it reads them from meters.csv):
//
//     floor    : a floors.yaml level key ("L00", …) — which floor page
//     column   : 0 | 1 | …                          — which column on that page
//     zone     : "West - Core 1" | …                — group key → floor-card title
//     position : integer                            — order within (floor, column)
//     function : "Fan Coil Units" | …               — short in-card label
//     utility  : a site.yaml utilities code ("electricity", "gas", …) — drives meter-<u> CSS.
//                A "-virtual" suffix ("lthw-virtual") marks a calculated
//                meter and gives meter-<u>-virtual, which the CSS colours
//                as its utility does plus a #2A0048 right-edge fade.
//     tenant   : "tenant-a" | "tenant-a,tenant-b" | …
//                — comma-separated slug(s); identifies which tenant pages
//                  show this meter. Filter is `<tenant_slug> in tenants`.
//
//   These properties are only emitted in the JS for meters where they're set,
//   mirroring the CSV row. Runtime code (data-meter-id auto-resolution) does
//   NOT read them — they exist purely for the build-time generator.
// ─────────────────────────────────────────────────────────────────────────────

// ── BEGIN GENERATED METER_REGISTRY ── DO NOT EDIT BY HAND ──
const METER_REGISTRY = [];
// ── END GENERATED METER_REGISTRY ──

// ─── POINTS ──────────────────────────────────────────────────────────────────
// Named non-meter BACnet points (BMS calculation points: NABERS rating, degree
// days, energy intensity, site sensors, …). This is the SINGLE source for these
// addresses — pages reference a point by name with `data-point="<name>"` and the
// resolver below fills in data-bacnet + data-format on load (mirroring
// data-meter-id). The block is written by the build from site/data/points.yaml
// — add or edit points there, once.
//
// Schema: <name>: { bacnet: "<device>|<object type>|<instance>|85|-1", format: "<fmt>" }
//   format ∈ number | energy | power | percentage | temperature | nabers | status
// ── BEGIN POINTS ──
const POINTS = {};
// ── END POINTS ──

// ─── BACNET_CONFIG ───────────────────────────────────────────────────────────
// This site's point addressing (see BACnet Address Rules above). Written by the
// build from site.yaml `bacnet:` — the same values the page generators use, so
// generated pages and runtime-resolved meters always agree. The build checks
// that every meter type in METER_REGISTRY has a powerOffset.
// ── BEGIN GENERATED BACNET_CONFIG ── DO NOT EDIT BY HAND ──
const BACNET_CONFIG = { device: null, powerOffset: {} };
// ── END GENERATED BACNET_CONFIG ──

// ─── Lookup map for O(1) access by meter id ──────────────────────────────────
const METER_BY_ID = {};
METER_REGISTRY.forEach(function(m) { METER_BY_ID[m.id] = m; });

// ─── Helpers ─────────────────────────────────────────────────────────────────

function slugify(tag) {
    return tag
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function getPowerOffset(type) {
    return BACNET_CONFIG.powerOffset[type];
}

function bacnet(objectType, objectInstance) {
    return BACNET_CONFIG.device + '|' + objectType + '|' + objectInstance + '|85|-1';
}

// ─── Field definitions ───────────────────────────────────────────────────────
const FIELD_CONFIG = {
    status: {
        getBacnet: function(meter) { return bacnet(3, meter.base); },
        format: 'status'
    },
    demand: {
        getBacnet: function(meter) { return bacnet(0, meter.base + getPowerOffset(meter.type)); },
        format: 'power'
    },
    energy: {
        getBacnet: function(meter) { return bacnet(0, meter.base); },
        format: 'energy'
    },
    daily: {
        getBacnet: function(meter) { return bacnet(0, meter.daily); },
        format: 'energy'
    },
    monthly: {
        getBacnet: function(meter) { return bacnet(0, meter.monthly); },
        format: 'energy'
    }
};

// ─── Public API ──────────────────────────────────────────────────────────────

function getMeter(meterId) {
    return METER_BY_ID[parseInt(meterId)] || null;
}

function getMeterDivId(meterId, field) {
    var meter = getMeter(meterId);
    if (!meter) return null;
    return 'live-' + slugify(meter.tag) + '-' + field;
}

function getMeterBacnet(meterId, field) {
    var meter = getMeter(meterId);
    var fieldCfg = FIELD_CONFIG[field];
    if (!meter || !fieldCfg) return null;
    return fieldCfg.getBacnet(meter);
}

// ─── Auto-resolve data-meter-id elements on DOM ready ────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var elements = document.querySelectorAll('[data-meter-id]');

    elements.forEach(function(el) {
        var meterId = el.getAttribute('data-meter-id');
        var field   = el.getAttribute('data-meter-field');

        if (!meterId || !field) {
            console.warn('Meter template: missing data-meter-id or data-meter-field', el);
            return;
        }

        var meter    = getMeter(meterId);
        var fieldCfg = FIELD_CONFIG[field];

        if (!meter) {
            console.error('Meter template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }
        if (!fieldCfg) {
            console.error('Meter template: unknown field "' + field + '"', el);
            el.textContent = 'Error: unknown field "' + field + '"';
            return;
        }

        // Set auto-generated id (only if not already set)
        if (!el.id) {
            el.id = 'live-' + slugify(meter.tag) + '-' + field;
        }

        // Set data-bacnet
        el.setAttribute('data-bacnet', fieldCfg.getBacnet(meter));

        // Set data-format (only if not already overridden)
        if (!el.getAttribute('data-format')) {
            el.setAttribute('data-format', fieldCfg.format);
        }

        // Set sensible defaults for status fields
        if (field === 'status') {
            if (!el.getAttribute('data-status-online-svg')) {
                el.setAttribute('data-status-online-svg', 'img/status-online.svg');
            }
            if (!el.getAttribute('data-status-offline-svg')) {
                el.setAttribute('data-status-offline-svg', 'img/status-offline.svg');
            }
        }

        // Set default refresh if not specified
        if (!el.getAttribute('data-refresh')) {
            el.setAttribute('data-refresh', '10');
        }
    });
});

// ─── Auto-resolve data-point elements on DOM ready ───────────────────────────
// Mirrors the data-meter-id resolver, but for named non-meter BACnet points
// (POINTS). Fills data-bacnet + data-format from the named point.
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-point]').forEach(function(el) {
        var name = el.getAttribute('data-point');
        var pt = POINTS[name];

        if (!pt) {
            console.error('Point template: unknown point "' + name + '"', el);
            el.textContent = 'Error: unknown point "' + name + '"';
            return;
        }

        el.setAttribute('data-bacnet', pt.bacnet);
        if (!el.getAttribute('data-format') && pt.format) {
            el.setAttribute('data-format', pt.format);
        }
        if (!el.getAttribute('data-refresh')) {
            el.setAttribute('data-refresh', '10');
        }
    });
});

// ─── Auto-resolve data-swb-meter elements on DOM ready ───────────────────────
// Generates the full switchboard meter widget (power link + status indicator)
// from a single placeholder element.
//
// Usage:
//   <div data-swb-meter="39" data-power-pos="557,679" data-status-pos="635,652"></div>
//
// Optional attributes:
//   data-online-svg   – status online SVG  (default: img/online-indicator.svg)
//   data-offline-svg  – status offline SVG (default: img/offline-indicator.svg)
//
// Generates:
//   <a href="/meters/MeterDisplay.html?meter.id=39" target="_blank" rel="noopener noreferrer">
//       <div id="live-tx1-demand" class="info-item-value data-overlay power loading"
//            data-position="557,679" data-bacnet="300|0|13840|85|-1"
//            data-format="power" data-refresh="10">Loading...</div>
//   </a>
//   <div id="live-tx1-status" class="info-item-value data-overlay"
//        data-position="635,652" data-bacnet="300|3|13800|85|-1"
//        data-format="status" data-refresh="10"
//        data-status-online-svg="img/online-indicator.svg"
//        data-status-offline-svg="img/offline-indicator.svg"
//        data-status-online-text=" " data-status-offline-text=" "
//        style="font-size: 10px;"></div>
// Run immediately (not DOMContentLoaded) — the script tag is at the bottom
// of <body>, so the data-swb-meter elements already exist in the DOM.
(function() {
    var elements = document.querySelectorAll('[data-swb-meter]');
    if (!elements.length) return;

    elements.forEach(function(el) {
        var meterId   = parseInt(el.getAttribute('data-swb-meter'));
        var powerPos  = el.getAttribute('data-power-pos');
        var statusPos = el.getAttribute('data-status-pos');

        if (!powerPos || !statusPos) {
            console.warn('SWB template: missing data-power-pos or data-status-pos', el);
            return;
        }

        var meter = getMeter(meterId);
        if (!meter) {
            console.error('SWB template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        var slug        = slugify(meter.tag);
        var powerBacnet = FIELD_CONFIG.demand.getBacnet(meter);
        var statusBcnt  = FIELD_CONFIG.status.getBacnet(meter);
        var onlineSvg   = el.getAttribute('data-online-svg')  || 'img/online-indicator.svg';
        var offlineSvg  = el.getAttribute('data-offline-svg') || 'img/offline-indicator.svg';

        // ── Power link ───────────────────────────────────────────────────
        var link = document.createElement('a');
        link.href   = '/meters/MeterDisplay.html?meter.id=' + meterId;
        link.target = '_blank';
        link.rel    = 'noopener noreferrer';

        var powerDiv = document.createElement('div');
        powerDiv.id        = 'live-' + slug + '-demand';
        powerDiv.className = 'info-item-value data-overlay power loading';
        powerDiv.setAttribute('data-position', powerPos);
        powerDiv.setAttribute('data-bacnet',   powerBacnet);
        powerDiv.setAttribute('data-format',   'power');
        powerDiv.setAttribute('data-refresh',  '10');
        powerDiv.textContent = 'Loading...';
        link.appendChild(powerDiv);

        // ── Status indicator ─────────────────────────────────────────────
        var statusDiv = document.createElement('div');
        statusDiv.id        = 'live-' + slug + '-status';
        statusDiv.className = 'info-item-value data-overlay';
        statusDiv.setAttribute('data-position',           statusPos);
        statusDiv.setAttribute('data-bacnet',             statusBcnt);
        statusDiv.setAttribute('data-format',             'status');
        statusDiv.setAttribute('data-refresh',            '10');
        statusDiv.setAttribute('data-status-online-svg',  onlineSvg);
        statusDiv.setAttribute('data-status-offline-svg', offlineSvg);
        statusDiv.setAttribute('data-status-online-text', ' ');
        statusDiv.setAttribute('data-status-offline-text',' ');
        statusDiv.style.fontSize = '10px';

        // ── Replace placeholder ──────────────────────────────────────────
        var parent = el.parentNode;
        parent.insertBefore(link, el);
        parent.insertBefore(statusDiv, el);
        parent.removeChild(el);
    });

    console.log('SWB template: resolved ' + elements.length + ' meter widgets');

    // Re-apply positioning after elements are created (position-handler may
    // not have loaded yet, so defer until it's available)
    setTimeout(function() {
        if (typeof window.applyDataPositions === 'function') {
            window.applyDataPositions();
        }
    }, 50);
})();

// ─── Auto-resolve data-floor-meter elements on DOM ready ─────────────────────
// Generates a full floor-card meter row (link + subheader + demand/month
// stat boxes) from a single placeholder element. Same idea as data-swb-meter,
// but for meters listed in a floor-card rather than positioned on an image —
// no data-power-pos / data-status-pos needed.
//
// Usage:
//   <div data-floor-meter="419"></div>
//
// Optional overrides (default to the meter registry's function/utility):
//   data-label    – subheader text, e.g. "LTHW"
//   data-utility  – meter-<utility> CSS class, e.g. "lthw"
//
// Generates:
//   <a href="/meters/MeterDisplay.html?meter.id=419" target="_blank" rel="noopener noreferrer" class="floor-stats-group-link">
//       <div class="floor-stats-group">
//           <div class="floor-stats-subheader meter-lthw floor-stats-subheader-flex">
//               <span>LTHW</span>
//               <div data-bacnet="..." data-format="status" data-refresh="10">Loading...</div>
//           </div>
//           <div class="floor-stats floor-stats-flex">
//               <div class="stat-box stat-box-flex">...Demand...</div>
//               <div class="stat-box stat-box-flex">...Current Month...</div>
//               <div class="stat-box stat-box-flex">...Previous Month...</div>
//           </div>
//       </div>
//   </a>
// Run immediately (not DOMContentLoaded) — the script tag is at the bottom
// of <body>, so the data-floor-meter elements already exist in the DOM.
(function() {
    // live-points.js's [data-bacnet] auto-scan keys everything off element.id
    // (DashboardLivePoints.init(element.id, ...)) — an element with no id
    // resolves to "" and fails with "Element with ID "" not found". Every
    // data-bacnet element built here needs one; -{field} keeps the several
    // per meter (status/demand/daily/monthly) unique.
    function meterDivId(meterId, field) {
        return 'meter-id-' + meterId + '-' + field;
    }

    function statBox(labelText, field, meter) {
        var fieldCfg = FIELD_CONFIG[field];
        var box = document.createElement('div');
        box.className = 'stat-box stat-box-flex';
        box.innerHTML =
            '<span class="stat-label">' + labelText + ':</span>' +
            '<span class="stat-value">' +
                '<span id="' + meterDivId(meter.id, field) + '" data-bacnet="' + fieldCfg.getBacnet(meter) + '" data-format="' + fieldCfg.format + '" data-refresh="10">Loading...</span>' +
            '</span>';
        return box;
    }

    // Shared by data-floor-meter and data-floor-stats: the Demand/Current
    // Month/Previous Month stat-box row every floor-card meter shows.
    function buildStatsBlock(meter) {
        var stats = document.createElement('div');
        stats.className = 'floor-stats floor-stats-flex';
        stats.appendChild(statBox('Demand', 'demand', meter));
        stats.appendChild(statBox('Current Month', 'daily', meter));
        stats.appendChild(statBox('Previous Month', 'monthly', meter));
        return stats;
    }

    var meterElements = document.querySelectorAll('[data-floor-meter]');
    meterElements.forEach(function(el) {
        var meterId = parseInt(el.getAttribute('data-floor-meter'));
        var meter = getMeter(meterId);

        if (!meter) {
            console.error('Floor meter template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        var label   = el.getAttribute('data-label')   || meter.function || meter.tag;
        var utility = el.getAttribute('data-utility') || meter.utility  || 'electricity';

        var link = document.createElement('a');
        link.href      = '/meters/MeterDisplay.html?meter.id=' + meterId;
        link.target    = '_blank';
        link.rel       = 'noopener noreferrer';
        link.className = 'floor-stats-group-link';

        var group = document.createElement('div');
        group.className = 'floor-stats-group';

        var subheader = document.createElement('div');
        subheader.className = 'floor-stats-subheader meter-' + utility + ' floor-stats-subheader-flex';
        subheader.innerHTML =
            '<span>' + label + '</span>' +
            '<div id="' + meterDivId(meterId, 'status') + '" data-bacnet="' + FIELD_CONFIG.status.getBacnet(meter) + '" data-format="status" data-refresh="10">Loading...</div>';

        group.appendChild(subheader);
        group.appendChild(buildStatsBlock(meter));
        link.appendChild(group);

        el.parentNode.replaceChild(link, el);
    });
    if (meterElements.length) {
        console.log('Floor meter template: resolved ' + meterElements.length + ' meter rows');
    }

    // ─── data-floor-stats: just the stat-box row, no subheader/link ─────────
    // For cards that already hand-render their own title/link elsewhere (see
    // floor_summary_card in macros.j2 — Total/Tenants/Landlords Electricity),
    // so the label doesn't get shown twice.
    //
    // Usage:
    //   <div data-floor-stats="588"></div>
    // Generates just the .floor-stats.floor-stats-flex block (Demand/Current
    // Month/Previous Month), same as the stats half of data-floor-meter.
    var statsElements = document.querySelectorAll('[data-floor-stats]');
    statsElements.forEach(function(el) {
        var meterId = parseInt(el.getAttribute('data-floor-stats'));
        var meter = getMeter(meterId);

        if (!meter) {
            console.error('Floor stats template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        el.parentNode.replaceChild(buildStatsBlock(meter), el);
    });
    if (statsElements.length) {
        console.log('Floor stats template: resolved ' + statsElements.length + ' stat rows');
    }
})();

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.MeterTemplates = {
        registry: METER_REGISTRY,
        points: POINTS,
        getMeter: getMeter,
        getMeterDivId: getMeterDivId,
        getMeterBacnet: getMeterBacnet,
        slugify: slugify
    };
}
