// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.

var OptergySpectrum = (function () {

    // -----------------------------------------------------------------------
    // Private: running counter so multiple widgets on one page get unique ids
    // -----------------------------------------------------------------------
    var _counter = 0;

    // -----------------------------------------------------------------------
    // Private: one-time Optergy global setup (idempotent)
    // -----------------------------------------------------------------------
    var _optergyInitialised = false;

    function _initOptergy() {
        if (_optergyInitialised) return;
        _optergyInitialised = true;

        if (typeof setRetriesAllowed === 'function') setRetriesAllowed(10);
        if (typeof setAOOverrideColor === 'function') setAOOverrideColor('rgb(255, 158, 94)');
        if (typeof setBVOverrideColor === 'function') setBVOverrideColor('rgb(255, 158, 94)');
        if (typeof setBOOverrideColor === 'function') setBOOverrideColor('rgb(255, 158, 94)');
    }

    // -----------------------------------------------------------------------
    // Private: build the dynamic overlay image URL
    //
    // Note: DOIPA values and numeric parameters are NOT percent-encoded
    // because the Optergy /images/dynamic/Overlay.png backend expects raw
    // pipe characters (|) and does not decode %7C.  Only the base image
    // path and colour values (which contain #) are encoded.
    // -----------------------------------------------------------------------
    function _buildImageUrl(cfg) {
        var url = '/images/dynamic/Overlay.png?doipa=' + cfg.doipa;

        if (cfg.image) {
            url += '&image=' + encodeURIComponent(cfg.image);
        }
        if (cfg.occupiedDoipa) {
            url += '&occupiedDoipa=' + cfg.occupiedDoipa;
        }
        if (cfg.transparency != null) {
            url += '&transparency=' + cfg.transparency;
        }

        // Mode 1: midpointDoipa – live BACnet midpoint
        if (cfg.midpointDoipa) {
            if (cfg.delta != null) {
                url += '&delta=' + cfg.delta;
            }
            url += '&midpointDoipa=' + cfg.midpointDoipa;
        }
        // Mode 2: midpointValue – fixed numeric midpoint
        else if (cfg.midpointValue != null) {
            if (cfg.delta != null) {
                url += '&delta=' + cfg.delta;
            }
            url += '&midpointValue=' + cfg.midpointValue;
        }
        // Mode 3: maps – custom colour ranges
        else if (cfg.maps && cfg.maps.length) {
            for (var i = 0; i < cfg.maps.length; i++) {
                var m = cfg.maps[i];
                var prefix = '&maps[' + i + '].';
                url += prefix + 'minValue=' + m.minValue;
                url += prefix + 'minInfinity=' + (m.minInfinity ? 'true' : 'false');
                url += prefix + 'maxValue=' + m.maxValue;
                url += prefix + 'maxInfinity=' + (m.maxInfinity ? 'true' : 'false');
                url += prefix + 'colour=' + encodeURIComponent(m.colour);
            }
        }
        // Fallback: include delta if provided even without midpoint (backwards compat)
        else if (cfg.delta != null) {
            url += '&delta=' + cfg.delta;
        }

        // cache-buster
        url += '&dm=' + Date.now();

        return url;
    }

    // -----------------------------------------------------------------------
    // Private: resolve a container argument to a DOM element
    // -----------------------------------------------------------------------
    function _resolveContainer(container) {
        if (typeof container === 'string') {
            return document.querySelector(container);
        }
        return container;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------
    return {

        /**
         * Create a spectrum overlay widget inside the given container.
         *
         * @param {Object} options
         * @param {string|Element} options.container        - CSS selector or DOM element to render into (required)
         * @param {string}         options.doipa             - Main BACnet DOIPA address, e.g. '300|0|111|85|-1' (required)
         * @param {string}        [options.image]            - Base image path relative to project, e.g. 'test/square.png'
         * @param {string}        [options.occupiedDoipa]    - DOIPA for the occupied-state data point
         * @param {string}        [options.midpointDoipa]    - DOIPA for the midpoint data point (Mode 1)
         * @param {number}        [options.midpointValue]    - Fixed numeric midpoint value (Mode 2)
         * @param {Array}         [options.maps]             - Array of colour range objects (Mode 3), each with:
         *                                                       minValue, minInfinity, maxValue, maxInfinity, colour
         * @param {number}        [options.transparency=130] - Overlay transparency (0-255)
         * @param {number}        [options.delta=5]          - Delta value for the spectrum calculation
         * @param {number}        [options.width]            - Image width in px (defaults to container width or 638)
         * @param {number}        [options.height]           - Image height in px (defaults to container height or 292)
         * @param {number}        [options.refreshSeconds=10]- Polling interval passed to assignImgWidget
         * @param {string}        [options.widgetId]         - Unique element id (auto-generated if omitted)
         * @param {string}        [options.title]            - Tooltip / title attribute for the image
         * @returns {HTMLImageElement}  The created <img> element (also stored as options._imgElement)
         */
        create: function (options) {
            if (!options || !options.container || !options.doipa) {
                console.error('[OptergySpectrum] "container" and "doipa" are required.');
                return null;
            }

            _initOptergy();

            var containerEl = _resolveContainer(options.container);
            if (!containerEl) {
                console.error('[OptergySpectrum] Container not found:', options.container);
                return null;
            }

            // Merge defaults
            var cfg = {
                doipa:          options.doipa,
                image:          options.image          || null,
                occupiedDoipa:  options.occupiedDoipa  || null,
                midpointDoipa:  options.midpointDoipa  || null,
                midpointValue:  options.midpointValue != null ? options.midpointValue : null,
                maps:           options.maps           || null,
                transparency:   options.transparency != null ? options.transparency : 130,
                delta:          options.delta != null ? options.delta : 5,
                width:          options.width          || containerEl.clientWidth  || 638,
                height:         options.height         || containerEl.clientHeight || 292,
                refreshSeconds: options.refreshSeconds != null ? options.refreshSeconds : 10,
                widgetId:       options.widgetId       || ('so' + _counter++),
                title:          options.title          || ('Spectrum – DOIPA ' + options.doipa)
            };

            // Build wrapper div (mirrors the structure in spectrum.htm)
            var wrapper = document.createElement('div');
            wrapper.style.cssText =
                'position:relative; overflow:hidden; width:' + cfg.width + 'px; height:' + cfg.height + 'px; border:0;';

            // Hover / highlight handlers (graceful degradation if functions missing)
            wrapper.onmouseover = function () {
                if (typeof highlight === 'function') highlight(wrapper, 0, 0, 0);
            };
            wrapper.onmouseout = function () {
                if (typeof unhighlight === 'function') unhighlight(wrapper, 0, '#000000', 0, 0);
            };

            // Build the <img> element
            var img = document.createElement('img');
            img.id = cfg.widgetId;
            img.title = cfg.title;
            img.border = '0';
            img.style.width = cfg.width + 'px';
            img.style.height = cfg.height + 'px';

            // The crucial onload: once the first image frame arrives, register
            // it with the Optergy live-update engine.
            img.onload = function () {
                if (typeof assignImgWidget === 'function') {
                    assignImgWidget(img, cfg.refreshSeconds);
                } else {
                    console.warn('[OptergySpectrum] assignImgWidget() not available – live refresh disabled.');
                }
                // Only register on the very first load
                img.onload = null;
            };

            img.src = _buildImageUrl(cfg);

            wrapper.appendChild(img);
            containerEl.appendChild(wrapper);

            // Store a reference for callers
            options._imgElement = img;

            return img;
        },

        /**
         * Initialise a spectrum widget from a single DOM element's data-* attributes.
         *
         * Reads the following data attributes from the element:
         *   data-doipa            (required)
         *   data-image
         *   data-occupied-doipa
         *   data-midpoint-doipa   (Mode 1: live BACnet midpoint)
         *   data-midpoint-value   (Mode 2: fixed numeric midpoint)
         *   data-maps             (Mode 3: JSON array of colour range objects)
         *   data-transparency
         *   data-delta
         *   data-width
         *   data-height
         *   data-refresh
         *   data-widget-id
         *   data-title
         *
         * The element itself becomes the container.
         *
         * @param {HTMLElement} el  The div element with data attributes
         * @returns {HTMLImageElement|null}
         */
        initFromDiv: function (el) {
            var doipa = el.getAttribute('data-doipa');
            if (!doipa) {
                console.error('[OptergySpectrum] data-doipa attribute is required on', el);
                return null;
            }

            var transparency = el.getAttribute('data-transparency');
            var delta        = el.getAttribute('data-delta');
            var width        = el.getAttribute('data-width');
            var height       = el.getAttribute('data-height');
            var refresh      = el.getAttribute('data-refresh');
            var midpointVal  = el.getAttribute('data-midpoint-value');

            // Parse maps from data-maps JSON attribute (Mode 3)
            var maps = null;
            var mapsAttr = el.getAttribute('data-maps');
            if (mapsAttr) {
                try {
                    maps = JSON.parse(mapsAttr);
                } catch (e) {
                    console.error('[OptergySpectrum] Could not parse data-maps JSON:', mapsAttr, e);
                }
            }

            return this.create({
                container:      el,
                doipa:          doipa,
                image:          el.getAttribute('data-image')          || undefined,
                occupiedDoipa:  el.getAttribute('data-occupied-doipa') || undefined,
                midpointDoipa:  el.getAttribute('data-midpoint-doipa') || undefined,
                midpointValue:  midpointVal !== null ? parseFloat(midpointVal) : undefined,
                maps:           maps                                   || undefined,
                transparency:   transparency !== null ? parseInt(transparency, 10) : undefined,
                delta:          delta        !== null ? parseInt(delta, 10)        : undefined,
                width:          width        !== null ? parseInt(width, 10)        : undefined,
                height:         height       !== null ? parseInt(height, 10)       : undefined,
                refreshSeconds: refresh      !== null ? parseInt(refresh, 10)      : undefined,
                widgetId:       el.getAttribute('data-widget-id')      || undefined,
                title:          el.getAttribute('data-title')          || undefined
            });
        },

        /**
         * Auto-initialise all elements on the page that have the
         * `data-optergy-spectrum` attribute.  Called automatically on
         * DOMContentLoaded, but can also be called manually.
         */
        autoInit: function () {
            var elements = document.querySelectorAll('[data-optergy-spectrum]');
            for (var i = 0; i < elements.length; i++) {
                // Skip elements already initialised
                if (elements[i].getAttribute('data-optergy-initialised')) continue;
                this.initFromDiv(elements[i]);
                elements[i].setAttribute('data-optergy-initialised', 'true');
            }

            // Run page-level init (touch support, checkReload, etc.)
            if (elements.length > 0) {
                this.initPage();
            }
        },

        /**
         * Initialise a spectrum widget by reading configuration from URL
         * query-string parameters.  Designed to be called from an HTML page
         * that includes this script, e.g. spectrum-widget.html.
         *
         * Supports all three modes:
         *   - midpointDoipa param  → Mode 1
         *   - midpointValue param  → Mode 2
         *   - maps[N].* params or maps JSON param → Mode 3
         */
        initFromUrl: function () {
            var params = new URLSearchParams(window.location.search);

            var doipa = params.get('doipa');
            if (!doipa) {
                var errEl = _resolveContainer(params.get('container') || '#spectrumContainer');
                if (errEl) {
                    errEl.innerHTML =
                        '<div style="color:#d32f2f;padding:20px;text-align:center;font-size:14px;">' +
                        'Error: <code>doipa</code> parameter is required.<br>' +
                        'Usage: <code>spectrum-widget.html?doipa=300|0|111|85|-1&amp;image=test/square.png</code>' +
                        '</div>';
                }
                return null;
            }

            // Parse maps from URL params (Mode 3)
            var maps = this._parseMapsFromUrl(params);

            // Parse midpointValue
            var midpointValue = params.has('midpointValue') ? parseFloat(params.get('midpointValue')) : undefined;

            return this.create({
                container:      params.get('container')      || '#spectrumContainer',
                doipa:          doipa,
                image:          params.get('image')          || null,
                occupiedDoipa:  params.get('occupiedDoipa')  || null,
                midpointDoipa:  params.get('midpointDoipa')  || null,
                midpointValue:  midpointValue,
                maps:           maps                         || null,
                transparency:   params.has('transparency')   ? parseInt(params.get('transparency'), 10) : undefined,
                delta:          params.has('delta')           ? parseInt(params.get('delta'), 10) : undefined,
                width:          params.has('width')           ? parseInt(params.get('width'), 10) : undefined,
                height:         params.has('height')          ? parseInt(params.get('height'), 10) : undefined,
                refreshSeconds: params.has('refresh')         ? parseInt(params.get('refresh'), 10) : undefined,
                widgetId:       params.get('widgetId')        || undefined,
                title:          params.get('title')           || undefined
            });
        },

        /**
         * Parse maps (colour ranges) from URL search params.
         * Supports both a JSON `maps` param and indexed `maps[N].*` params.
         *
         * @param {URLSearchParams} params
         * @returns {Array|null}
         */
        _parseMapsFromUrl: function (params) {
            // Try JSON first
            var mapsJson = params.get('maps');
            if (mapsJson) {
                try {
                    var parsed = JSON.parse(mapsJson);
                    if (Array.isArray(parsed)) return parsed;
                } catch (e) { /* not JSON, try indexed form */ }
            }

            // Indexed form: maps[N].minValue, maps[N].maxValue, maps[N].colour, etc.
            var maps = [];
            var i = 0;
            while (true) {
                var minVal  = params.get('maps[' + i + '].minValue');
                var maxVal  = params.get('maps[' + i + '].maxValue');
                var colour  = params.get('maps[' + i + '].colour');
                if (minVal === null && maxVal === null && colour === null) break;

                var minInf = params.get('maps[' + i + '].minInfinity');
                var maxInf = params.get('maps[' + i + '].maxInfinity');

                maps.push({
                    minValue:    minVal  !== null ? parseFloat(minVal) : 0,
                    maxValue:    maxVal  !== null ? parseFloat(maxVal) : 0,
                    minInfinity: minInf === 'true',
                    maxInfinity: maxInf === 'true',
                    colour:      colour || ''
                });
                i++;
            }

            return maps.length > 0 ? maps : null;
        },

        /**
         * Convenience: call after jQuery is ready to wire up touch support
         * and the standard Optergy body-onload sequence.
         */
        initPage: function () {
            _initOptergy();

            if (typeof $ !== 'undefined') {
                $.extend($.support, { touch: 'ontouchend' in document });
                $(function () {
                    if ($.fn.addTouch) {
                        $('img').addTouch();
                    }
                });
            }

            if (typeof checkReload === 'function') checkReload();
            if (typeof hideAllDisplayOnHover === 'function') hideAllDisplayOnHover();
        }
    };

})();

// -----------------------------------------------------------------------
// Auto-initialise on DOMContentLoaded
// -----------------------------------------------------------------------
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            OptergySpectrum.autoInit();
        });
    } else {
        // DOM already ready (script loaded dynamically or with defer)
        OptergySpectrum.autoInit();
    }
}
