// ─── Report images ───────────────────────────────────────────────────────────
// ReportUrls.reports.<image_ref> ← the chart image URL behind every report card.
// Pages carry data-image-ref="reports.<image_ref>"; the loader below swaps in
// the URL on DOM ready (report_template.htm resolves its own the same way).
//
// The GENERATED REPORT_URLS block is written by the build from
// site/data/reports.yaml `urls:` — edit URLs there, not here. Which page/slot
// each report card appears on (reports.yaml `placements:`) is build-time only
// and isn't shipped.
// ─────────────────────────────────────────────────────────────────────────────

// ── BEGIN GENERATED REPORT_URLS ── DO NOT EDIT BY HAND ──
const ReportUrls = { reports: {} };
// ── END GENERATED REPORT_URLS ──


// Initialize images when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
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

