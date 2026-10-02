/* ─────────────────────────────────────────────────────────────────────────
   energy-dials.js — live segmented-dial KPI widget.

   Wraps EnergyCharts.segmentedDial (from energy-charts.js) and drives it from a
   live Optergy BACnet point, reusing the project's live-points mechanism. A
   dial is a horizontal segmented gauge with a big live value.

   Requires (loaded first): js/d3/7/d3.v7.min.js, js/d3/7/energy-charts.js, and
   js/project/2.0/live-points.js (already loaded by base.html.j2).

   ── Declarative (drop-in template) ───────────────────────────────────────
       <div class="energy-dial"
            data-dial-bacnet="300|2|71|85|-1"   <!-- the live point -->
            data-format="power"                  <!-- power → kW suffix -->
            data-label="Cooling Demand"
            data-min="0" data-max="200" data-refresh="10"></div>

   NOTE the container uses data-DIAL-bacnet (not data-bacnet) so the generic
   live-points binder ignores it; this script renders the dial into the
   container and creates its own hidden data-bacnet element to poll the value.

   ── Programmatic ─────────────────────────────────────────────────────────
       EnergyDials.create("#myDial", {
         bacnet: "300|2|71|85|-1", label: "Cooling Demand",
         format: "power", min: 0, max: 200, refresh: 10
       });

   Every dial auto-initialises on DOMContentLoaded.
   ───────────────────────────────────────────────────────────────────────── */
(function (global) {
  "use strict";

  var counter = 0;

  // data-format → default value suffix (mirrors live-points' FORMAT_CONFIG units).
  var SUFFIX = {
    power: " kW", energy: " kWh", temperature: " °C", percentage: " %",
    water: " m³", gas: " m³", voltage: " V", current: " A", cost: "", number: "",
  };

  function parseNumber(text) {
    if (text == null) return NaN;
    return parseFloat(String(text).replace(/,/g, "").replace(/[^0-9.\-]/g, ""));
  }

  // Observe the live element's text (Optergy writes into a child _text span);
  // call back with the parsed number whenever it changes.
  function observe(el, cb) {
    var apply = function () {
      var v = parseNumber(el.textContent);
      if (isFinite(v)) cb(v);
    };
    new MutationObserver(apply).observe(el, { childList: true, characterData: true, subtree: true });
    apply();
  }

  function num(v, dflt) { return v == null || v === "" ? dflt : +v; }

  function create(container, cfg) {
    cfg = cfg || {};
    var host = typeof container === "string" ? document.querySelector(container) : container;
    if (!host) return null;
    if (!global.EnergyCharts || !global.EnergyCharts.segmentedDial) {
      console.error("EnergyDials: energy-charts.js (window.EnergyCharts.segmentedDial) not loaded.");
      return null;
    }

    var format = cfg.format || null;
    var width = num(cfg.width, 600);
    var height = num(cfg.height, 200);

    var opts = {
      label: cfg.label || "",
      min: num(cfg.min, 0),
      max: num(cfg.max, 100),
      decimals: num(cfg.decimals, 0),
      suffix: cfg.suffix != null ? cfg.suffix : (SUFFIX[format] != null ? SUFFIX[format] : ""),
      offColor: cfg.offColor || "rgba(127,127,127,0.18)",
      width: width,
      height: height,
    };
    if (cfg.segments) opts.segments = +cfg.segments;
    if (cfg.zones) opts.zones = cfg.zones;

    // Visible dial canvas
    var box = document.createElement("div");
    box.className = "energy-dial-canvas";
    host.appendChild(box);
    var dial = global.EnergyCharts.segmentedDial(box, opts.min, opts);

    // The library renders a fixed-size <svg>; give it a viewBox so it scales
    // to the card width (and drop the fixed width/height attrs).
    var svg = box.querySelector("svg");
    if (svg) {
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      svg.removeAttribute("width");
      svg.removeAttribute("height");
    }

    // Hidden live source — bound by live-points.js via data-bacnet — feeds the dial.
    if (cfg.bacnet) {
      var src = document.createElement("div");
      src.id = "energy-dial-src-" + (++counter);
      src.className = "energy-dial-src";
      src.setAttribute("data-bacnet", cfg.bacnet);
      src.setAttribute("data-refresh", cfg.refresh || 10);
      src.textContent = "Loading...";
      host.appendChild(src);
      observe(src, function (v) { dial.update(v); });
    }

    return dial;
  }

  function autoInit() {
    var els = document.querySelectorAll(".energy-dial[data-dial-bacnet]");
    Array.prototype.forEach.call(els, function (el) {
      if (el.getAttribute("data-dial-init")) return;
      el.setAttribute("data-dial-init", "1");
      create(el, {
        bacnet:   el.getAttribute("data-dial-bacnet"),
        format:   el.getAttribute("data-format"),
        label:    el.getAttribute("data-label"),
        min:      el.getAttribute("data-min"),
        max:      el.getAttribute("data-max"),
        decimals: el.getAttribute("data-decimals") || el.getAttribute("data-decimal-places"),
        suffix:   el.getAttribute("data-suffix"),
        refresh:  el.getAttribute("data-refresh"),
        width:    el.getAttribute("data-width"),
        height:   el.getAttribute("data-height"),
        segments: el.getAttribute("data-segments"),
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit);
  } else {
    autoInit();
  }

  global.EnergyDials = { create: create, autoInit: autoInit };
})(window);
