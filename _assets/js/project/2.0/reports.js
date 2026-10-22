// ─── Report images ───────────────────────────────────────────────────────────
// ReportUrls.reports.<image_ref> ← the chart image URL behind every report card.
// Pages carry data-image-ref="reports.<image_ref>"; the loader below swaps in
// the URL on DOM ready (report_template.htm resolves its own the same way).
//
// The GENERATED REPORT_URLS block is written by the build from
// site/data/reports.yaml `urls:` — edit URLs there, not here.
// ─────────────────────────────────────────────────────────────────────────────

// ── BEGIN GENERATED REPORT_URLS ── DO NOT EDIT BY HAND ──
const ReportUrls = { reports: {} };
// ── END GENERATED REPORT_URLS ──

// ─── Report cards ────────────────────────────────────────────────────────────
// A page asks for a report card by name, in one line:
//
//   <div data-report="floor_2nd_electricity_demand"></div>
//
// and the loader below replaces it with the card: the chart
// (ReportUrls.reports.<name>) under a header, linking to the report in the
// Optergy report library (# without an id). The card's `kind` is its style:
//
//   (none)  plain: floor tabs, tenant and incomer pages; a header band with
//           its title, when it has one
//   headed  home (and a `kind: headed` incomer card): a header band
//   titled  building performance: a title and a subtitle
//
// The GENERATED REPORT_CARDS block is written by the build from
// site/data/reports.yaml `placements:`: each report's kind, title, subtitle,
// alt text and library item id. Which page/slot a card appears on stays
// build-time only.
// ─────────────────────────────────────────────────────────────────────────────

// ── BEGIN GENERATED REPORT_CARDS ── DO NOT EDIT BY HAND ──
const REPORT_CARDS = {};
// ── END GENERATED REPORT_CARDS ──

function escapeReportHtml(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function reportCardHtml(name, card) {
    var esc = escapeReportHtml;
    function link(cls) {
        return card.libraryItemId !== undefined
            ? '<a href="/utilityReports/UtilityReports.html?libraryItemId=' + encodeURIComponent(card.libraryItemId) +
              '" target="_blank" rel="noopener noreferrer" class="' + cls + '">'
            : '<a href="#" class="' + cls + '">';
    }
    function line(cls, text) {
        return text !== undefined ? '<div class="' + cls + '">' + esc(text) + '</div>' : '';
    }
    var header = card.kind === 'titled'
        ? line('report-title', card.title) + line('report-subtitle', card.subtitle)
        : line('floor-title', card.title);
    if (header) {
        header = '<div class="report-header">' + header + '</div>';
    }
    var chart = '<div class="report-content"><img data-image-ref="reports.' + esc(name) + '"' +
        ' alt="' + esc(card.alt !== undefined ? card.alt : 'Report') + '"' +
        ' style="max-width: 100%; height: auto; display: block;"></div>';

    if (card.kind === 'headed') {
        return link('floor-stats-group-link') + '<div class="report-placeholder">' + header + chart + '</div></a>';
    }
    if (card.kind === 'titled') {
        return link('floor-card') + '<div class="report-placeholder">' + header + chart + '</div></a>';
    }
    return link('floor-card') +
        '<div class="floorplan-viewer"><div class="floorplan-placeholder">' + header + chart + '</div></div></a>';
}

// Initialize report cards and images when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Build each <div data-report="<name>"> into its card
    document.querySelectorAll('[data-report]').forEach(function(el) {
        var name = el.getAttribute('data-report');
        var own = Object.prototype.hasOwnProperty;
        if (!own.call(ReportUrls.reports, name)) {
            console.warn('reports.js: no chart URL for data-report="' + name + '"');
            return;
        }
        el.outerHTML = reportCardHtml(name, own.call(REPORT_CARDS, name) ? REPORT_CARDS[name] : {});
    });

    // Set image src for elements with data-image-ref attribute
    document.querySelectorAll('[data-image-ref]').forEach(function(img) {
        const refPath = img.getAttribute('data-image-ref').split('.');
        let url = ReportUrls;

        // Navigate through the object path
        refPath.forEach(function(key) {
            url = url[key];
        });

        if (url) {
            img.src = url;
        }
    });
});
