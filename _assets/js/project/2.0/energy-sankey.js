/* ─────────────────────────────────────────────────────────────────────────
   energy-sankey.js — D3 Sankey energy-flow diagram (with live data).

   Ported from d3/sankey-energy.html into a reusable module. Requires the
   self-hosted d3 + d3-sankey bundles (js/d3/7/) loaded first — no CDN, runs
   fully offline.

   Usage:
       var chart = EnergySankey.render("#sankey", data);
       chart.setFlow("Electricity", "Landlord", 420);  // programmatic update

   `data` shape (source/target may be a node name or an index):
       {
         nodes: [ { name: "Electricity", color: "#2f81f7" }, ... ],
         links: [ { source: "Electricity", target: "Landlord", value: 400 }, ... ],
         unit:  "MWh"
       }

   ── Live values (Optergy backend) ───────────────────────────────────────
   Every flow is driven live. Each link carries `meters: [...]` of source
   tokens and its live value is the SUM of those sources. The page emits one
   hidden element per UNIQUE token, tagged with data-sankey-meter=<token>.
   Two source kinds are supported (both observed identically):

     • registry meter (token = numeric id) — uses the standard data-meter-id
       mechanism; meter-templates.js resolves it to a data-bacnet:
         <div class="sankey-live" data-sankey-meter="27"
              data-meter-id="27" data-meter-field="demand" data-refresh="10">…</div>

     • raw BACnet point (token = a string key) — a calculated/explicit point,
       bound directly by live-points.js (no registry lookup):
         <div class="sankey-live" data-sankey-meter="gas"
              data-bacnet="300|2|71|85|-1" data-format="power" data-refresh="10">…</div>

   live-points.js writes the value into the element; this module observes each
   element's text and, when a source updates, re-sums every flow that
   references that token and re-lays-out. A source shared by several flows is
   polled only once. The static `value` on a link is the initial width shown
   until live readings arrive.

   On the generated page the data is emitted into a
   <script type="application/json" id="sankey-data"> block by the Jinja
   template and auto-rendered on DOMContentLoaded (see bottom of file).
   ───────────────────────────────────────────────────────────────────────── */
(function (global) {
  "use strict";

  function render(svgSelector, data, options) {
    options = options || {};
    var unit = options.unit || data.unit || "MWh";

    if (!global.d3 || !global.d3.sankey) {
      console.error("EnergySankey: d3 and d3-sankey must be loaded first.");
      return null;
    }
    var d3 = global.d3;

    var svg = d3.select(svgSelector);
    if (svg.empty()) return null;
    svg.selectAll("*").remove(); // idempotent re-render

    var width = +svg.attr("width");
    var height = +svg.attr("height");
    var fmt = d3.format(",");

    // ---------- Raw, mutable arrays (the source of truth for relayout) ----------
    var index = new Map(data.nodes.map(function (n, i) { return [n.name, i]; }));
    var rawNodes = data.nodes.map(function (d) { return Object.assign({}, d); });
    var rawLinks = data.links.map(function (l) {
      var s = typeof l.source === "number" ? l.source : index.get(l.source);
      var t = typeof l.target === "number" ? l.target : index.get(l.target);
      return { source: s, target: t, value: +l.value || 0, meters: l.meters || [] };
    });

    // Map "sourceIdx-targetIdx" → rawLinks index, for live updates by node name.
    var linkByKey = new Map();
    rawLinks.forEach(function (l, i) { linkByKey.set(l.source + "-" + l.target, i); });

    // source token → [link indices that sum it]; current live reading per token.
    // A token is a registry meter id (number) or a raw-point key (string); both
    // are keyed as strings so the two live paths share one map.
    var meterToLinks = new Map();
    rawLinks.forEach(function (l, i) {
      l.meters.forEach(function (mid) {
        var key = String(mid);
        if (!meterToLinks.has(key)) meterToLinks.set(key, []);
        meterToLinks.get(key).push(i);
      });
    });
    var meterValue = new Map();

    var sankeyLayout = d3.sankey()
      .nodeWidth(18)
      .nodePadding(14)
      .nodeAlign(d3.sankeyJustify) // push sink nodes (end uses) to the last column
      .extent([[8, 12], [width - 8, height - 12]]);

    // Persistent <g> layers so links always sit under nodes.
    var linkLayer = svg.append("g").attr("class", "sankey-links");
    var nodeLayer = svg.append("g").attr("class", "sankey-nodes");
    var graph;

    function recompute() {
      // Rebuild from raw arrays each time so changing link.value re-flows the
      // whole diagram cleanly (d3-sankey mutates its inputs, hence the copies).
      graph = sankeyLayout({
        nodes: rawNodes.map(function (d) { return Object.assign({}, d); }),
        links: rawLinks.map(function (d) { return Object.assign({}, d); }),
      });
    }

    function labelX(d) { return d.x0 < width / 2 ? d.x1 + 8 : d.x0 - 8; }
    function labelAnchor(d) { return d.x0 < width / 2 ? "start" : "end"; }

    function draw(animate) {
      var dur = animate ? 600 : 0;

      // ---------- Links ----------
      var linkSel = linkLayer.selectAll("path.link")
        .data(graph.links, function (d) { return d.source.index + "-" + d.target.index; });

      linkSel.exit().remove();

      var linkEnter = linkSel.enter().append("path")
        .attr("class", "link")
        .attr("stroke", function (d) { return d.source.color; })
        .attr("stroke-opacity", 0.38)
        .attr("d", d3.sankeyLinkHorizontal());
      linkEnter.append("title");

      var linkAll = linkEnter.merge(linkSel);
      linkAll.select("title")
        .text(function (d) {
          return d.source.name + " → " + d.target.name + "\n" + fmt(Math.round(d.value)) + " " + unit;
        });
      linkAll.transition().duration(dur)
        .attr("d", d3.sankeyLinkHorizontal())
        .attr("stroke-width", function (d) { return Math.max(1, d.width); });

      // ---------- Nodes ----------
      var nodeSel = nodeLayer.selectAll("g.node")
        .data(graph.nodes, function (d) { return d.index; });

      nodeSel.exit().remove();

      var nodeEnter = nodeSel.enter().append("g").attr("class", "node");
      nodeEnter.append("rect")
        .attr("fill", function (d) { return d.color; })
        .attr("rx", 3)
        .attr("width", function (d) { return d.x1 - d.x0; });
      nodeEnter.append("title");
      var labelEnter = nodeEnter.append("text")
        .attr("class", "node-label")
        .attr("dy", "0.35em");
      labelEnter.append("tspan").attr("class", "node-name");
      labelEnter.append("tspan").attr("class", "node-value");

      var nodeAll = nodeEnter.merge(nodeSel);
      nodeAll.select("title")
        .text(function (d) { return d.name + "\n" + fmt(Math.round(d.value)) + " " + unit; });
      nodeAll.select("rect").transition().duration(dur)
        .attr("x", function (d) { return d.x0; })
        .attr("y", function (d) { return d.y0; })
        .attr("height", function (d) { return Math.max(1, d.y1 - d.y0); })
        .attr("width", function (d) { return d.x1 - d.x0; });
      nodeAll.select("text")
        .attr("text-anchor", labelAnchor)
        .transition().duration(dur)
        .attr("x", labelX)
        .attr("y", function (d) { return (d.y0 + d.y1) / 2; });
      nodeAll.select("tspan.node-name").text(function (d) { return d.name; });
      nodeAll.select("tspan.node-value").text(function (d) { return "  " + fmt(Math.round(d.value)); });

      // ---------- Dragging ----------
      nodeAll.style("cursor", "grab").call(drag);
    }

    // ---------- Drag (manual exploration; live updates re-flow on top) ----------
    function reposition(sel) {
      sel.select("rect").attr("x", function (d) { return d.x0; }).attr("y", function (d) { return d.y0; });
      sel.select("text")
        .attr("x", labelX)
        .attr("y", function (d) { return (d.y0 + d.y1) / 2; })
        .attr("text-anchor", labelAnchor);
    }

    var drag = d3.drag()
      .subject(function (d) { return d; })
      .on("start", function () {
        this.parentNode.appendChild(this);
        d3.select(this).select("rect").attr("stroke", "#e6edf3").attr("stroke-width", 1.5);
      })
      .on("drag", function (event, d) {
        var w = d.x1 - d.x0, h = d.y1 - d.y0;
        d.x0 = Math.max(0, Math.min(width - w, d.x0 + event.dx));
        d.x1 = d.x0 + w;
        d.y0 = Math.max(0, Math.min(height - h, d.y0 + event.dy));
        d.y1 = d.y0 + h;
        reposition(d3.select(this));
        sankeyLayout.update(graph);
        linkLayer.selectAll("path.link").attr("d", d3.sankeyLinkHorizontal());
      })
      .on("end", function () {
        d3.select(this).select("rect").attr("stroke", "rgba(0,0,0,0.3)").attr("stroke-width", 1);
      });

    // ---------- Public update API ----------
    // Coalesce rapid live updates (several flows may refresh together) into one
    // relayout on the next animation frame.
    var pending = false;
    function scheduleRedraw() {
      if (pending) return;
      pending = true;
      global.requestAnimationFrame(function () {
        pending = false;
        recompute();
        draw(true);
      });
    }

    function setLinkValue(i, v) {
      if (i === undefined || !isFinite(v) || v < 0) return false;
      if (rawLinks[i].value === v) return false;
      rawLinks[i].value = v;
      scheduleRedraw();
      return true;
    }

    // Public: set a single flow by node name (or index) to an absolute value.
    function setFlow(source, target, value) {
      var si = typeof source === "number" ? source : index.get(source);
      var ti = typeof target === "number" ? target : index.get(target);
      var i = linkByKey.get(si + "-" + ti);
      if (i === undefined) {
        console.warn("EnergySankey: no flow " + source + " → " + target + " to update.");
        return false;
      }
      return setLinkValue(i, +value);
    }

    // Record a source's latest reading (by token) and re-sum every flow that
    // includes it. Token = registry meter id or raw-point key, matched as a string.
    function ingestMeter(token, value) {
      token = String(token);
      meterValue.set(token, value);
      var affected = meterToLinks.get(token);
      if (!affected) return;
      affected.forEach(function (i) {
        var sum = 0;
        rawLinks[i].meters.forEach(function (mid) {
          var k = String(mid);
          if (meterValue.has(k)) sum += meterValue.get(k);
        });
        setLinkValue(i, sum);
      });
    }

    recompute();
    draw(false);

    bindLiveMeters(ingestMeter);
    return { svg: svg.node(), setFlow: setFlow, ingestMeter: ingestMeter, redraw: scheduleRedraw };
  }

  // ---------- Live binding via the project's data-meter-id mechanism ----------
  // Watch the text Optergy writes into each hidden meter element and feed the
  // parsed number to ingestMeter(). Works regardless of script order:
  // meter-templates.js / live-points.js populate the element on their own
  // DOMContentLoaded timers; the observer just reacts when text appears.
  function parseNumber(text) {
    if (text == null) return NaN;
    // Strip thousands separators and any unit/label, keep sign + digits + dot.
    var cleaned = String(text).replace(/,/g, "").replace(/[^0-9.\-]/g, "");
    return parseFloat(cleaned);
  }

  function bindLiveMeters(ingest) {
    // Each hidden source element carries data-sankey-meter = its token (a
    // registry meter id, OR a raw-point key whose value comes via data-bacnet).
    var els = document.querySelectorAll(".sankey-live[data-sankey-meter]");
    if (!els.length) return;

    els.forEach(function (el) {
      var token = el.getAttribute("data-sankey-meter");

      var apply = function () {
        var v = parseNumber(el.textContent);
        if (isFinite(v)) ingest(token, v);
      };

      // The value lands inside a child span (#<id>_text) that Optergy creates
      // and updates; observing the element with subtree covers it.
      var observer = new MutationObserver(apply);
      observer.observe(el, { childList: true, characterData: true, subtree: true });

      apply(); // in case a value is already present
    });
  }

  // ---------- Auto-init from inline JSON ----------
  function autoInit() {
    var holder = document.getElementById("sankey-data");
    if (!holder) return;
    var data;
    try {
      data = JSON.parse(holder.textContent);
    } catch (e) {
      console.error("EnergySankey: could not parse #sankey-data JSON.", e);
      return;
    }
    global.energySankey = render("#sankey", data, { unit: data.unit || "MWh" });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit);
  } else {
    autoInit();
  }

  global.EnergySankey = { render: render };
})(window);
