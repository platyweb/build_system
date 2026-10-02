// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.

// ─── Switchboard segmented gauge ─────────────────────────────────────────────
// Renders the segmented horizontal gauge inside each .swb-box and keeps it in
// sync with the live value. It does NOT fetch data itself — live-points.js
// writes the formatted value into the sibling .swb-value element; this module
// watches that element and repaints the gauge (and the box's load-status class)
// whenever it changes.
//
// Per box:
//   <div class="swb-gauge" data-max="250"></div>   ← full-scale (kW) for 100%
//   <span class="swb-value" ...>123 kW</span>       ← live text from live-points
//
// Threshold colors match d3/segmented-horizontal: grey <10, green 10–70,
// yellow 70–85, red 85–100. Load status (ok/warn/alarm) is derived from the
// percentage and applied as a class on the .swb-box (drives dot + border).

(function () {
    'use strict';

    var SEGMENTS = 14;
    var OFF = 'rgba(0,0,0,0.10)';

    function hexToRgb(h) {
        h = h.replace('#', '');
        return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    }
    function lerp(a, b, t) {
        var A = hexToRgb(a), B = hexToRgb(b);
        function c(i) { return Math.round(A[i] + (B[i] - A[i]) * t); }
        return 'rgb(' + c(0) + ',' + c(1) + ',' + c(2) + ')';
    }
    function segColor(pct) {
        if (pct < 10) return '#6e7681';
        if (pct < 70) return lerp('#56d364', '#1a7f37', (pct - 10) / 60);
        if (pct < 85) return lerp('#f2cc60', '#bb8009', (pct - 70) / 15);
        return lerp('#ff7b72', '#b62324', (pct - 85) / 15);
    }
    function statusFromPct(pct) {
        return pct >= 85 ? 'alarm' : pct >= 70 ? 'warn' : 'ok';
    }

    // pull the first number out of e.g. "123.4 kW" / "1,234 kW"
    function parseValue(text) {
        if (!text) return NaN;
        var m = text.replace(/,/g, '').match(/-?\d+(\.\d+)?/);
        return m ? parseFloat(m[0]) : NaN;
    }

    function buildSegments(gauge) {
        var segs = [];
        for (var i = 0; i < SEGMENTS; i++) {
            var s = document.createElement('span');
            s.className = 'seg';
            gauge.appendChild(s);
            segs.push(s);
        }
        return segs;
    }

    function makeRenderer(box, gauge, segs, valueEl) {
        var max = parseFloat(gauge.getAttribute('data-max')) || 0;
        return function render() {
            var val = parseValue(valueEl ? valueEl.textContent : '');
            var hasVal = isFinite(val) && max > 0;
            var pct = hasVal ? Math.max(0, Math.min(100, (val / max) * 100)) : 0;
            var lit = Math.round((pct / 100) * SEGMENTS);
            for (var i = 0; i < SEGMENTS; i++) {
                segs[i].style.background = i < lit ? segColor(((i + 0.5) / SEGMENTS) * 100) : OFF;
            }
            box.classList.remove('status-ok', 'status-warn', 'status-alarm');
            if (hasVal) box.classList.add('status-' + statusFromPct(pct));
        };
    }

    function init() {
        var gauges = document.querySelectorAll('.swb-gauge');
        gauges.forEach(function (gauge) {
            var box = gauge.closest('.swb-box');
            var valueEl = box ? box.querySelector('.swb-value') : null;
            var segs = buildSegments(gauge);
            var render = makeRenderer(box, gauge, segs, valueEl);
            render();
            if (valueEl) {
                new MutationObserver(render).observe(valueEl, {
                    childList: true, characterData: true, subtree: true,
                });
            }
        });
        console.log('switchboard-gauge: initialised ' + gauges.length + ' gauge(s)');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
