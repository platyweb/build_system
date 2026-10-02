// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.

var OptergyRange = (function () {

    // -----------------------------------------------------------------------
    // Private: running counter so multiple widgets get unique ids
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
    // Private: build the dynamic Range image URL
    // -----------------------------------------------------------------------
    function _buildImageUrl(cfg) {
        // Note: the DOIPA and numeric values are NOT percent-encoded because
        // the Optergy /images/dynamic/Range.png backend expects raw pipe
        // characters (|) and does not decode %7C.  Only the image path is
        // encoded (forward-slashes → %2F) to match the original range.html
        // URL format.
        var url = '/images/dynamic/Range.png?doipa=' + cfg.doipa;

        if (cfg.maps && cfg.maps.length) {
            for (var i = 0; i < cfg.maps.length; i++) {
                var m = cfg.maps[i];
                var prefix = '&maps[' + i + '].';
                url += prefix + 'minValue=' + m.minValue;
                url += prefix + 'maxValue=' + m.maxValue;
                url += prefix + 'image='    + encodeURIComponent(m.image);
            }
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
    // Private: parse maps from URL search params
    // -----------------------------------------------------------------------
    function _parseMapsFromUrl(params) {
        // Try JSON first
        var mapsJson = params.get('maps');
        if (mapsJson) {
            try {
                var parsed = JSON.parse(mapsJson);
                if (Array.isArray(parsed)) return parsed;
            } catch (e) { /* not JSON, try indexed form */ }
        }

        // Indexed form: maps[N].minValue, maps[N].maxValue, maps[N].image
        var maps = [];
        var i = 0;
        while (true) {
            var minVal = params.get('maps[' + i + '].minValue');
            var maxVal = params.get('maps[' + i + '].maxValue');
            var img    = params.get('maps[' + i + '].image');
            if (minVal === null && maxVal === null && img === null) break;
            maps.push({
                minValue: minVal !== null ? parseFloat(minVal) : 0,
                maxValue: maxVal !== null ? parseFloat(maxVal) : 0,
                image:    img || ''
            });
            i++;
        }

        return maps.length > 0 ? maps : null;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------
    return {

        /**
         * Create a range image widget inside the given container.
         *
         * @param {Object} options
         * @param {string|Element} options.container       - CSS selector or DOM element (required)
         * @param {string}         options.doipa            - BACnet DOIPA address (required)
         * @param {Array}          options.maps             - Array of {minValue, maxValue, image} (required)
         * @param {number}        [options.width]           - Image width in px (default: container or 239)
         * @param {number}        [options.height]          - Image height in px (default: container or 173)
         * @param {number}        [options.refreshSeconds=10] - Polling interval for assignImgWidget
         * @param {string}        [options.widgetId]        - Unique element id (auto-generated)
         * @param {string}        [options.title]           - Tooltip text
         * @returns {HTMLImageElement}  The created <img> element
         */
        create: function (options) {
            if (!options || !options.container || !options.doipa) {
                console.error('[OptergyRange] "container" and "doipa" are required.');
                return null;
            }
            if (!options.maps || !options.maps.length) {
                console.error('[OptergyRange] "maps" array is required (at least one range mapping).');
                return null;
            }

            _initOptergy();

            var containerEl = _resolveContainer(options.container);
            if (!containerEl) {
                console.error('[OptergyRange] Container not found:', options.container);
                return null;
            }

            // Merge defaults
            var cfg = {
                doipa:          options.doipa,
                maps:           options.maps,
                width:          options.width          || containerEl.clientWidth  || 239,
                height:         options.height         || containerEl.clientHeight || 173,
                refreshSeconds: options.refreshSeconds != null ? options.refreshSeconds : 10,
                widgetId:       options.widgetId       || ('xf' + _counter++),
                title:          options.title          || ('Range – DOIPA ' + options.doipa)
            };

            // Wrapper div (mirrors range.html structure)
            var wrapper = document.createElement('div');
            wrapper.title = cfg.title;
            wrapper.style.cssText =
                'position:relative; overflow:hidden; width:' + cfg.width + 'px; height:' + cfg.height + 'px; border:0;';

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
            img.className = 'prompted';
            img.style.width = cfg.width + 'px';
            img.style.height = cfg.height + 'px';

            // On first load register with Optergy live-update engine
            img.onload = function () {
                if (typeof assignImgWidget === 'function') {
                    assignImgWidget(img, cfg.refreshSeconds);
                } else {
                    console.warn('[OptergyRange] assignImgWidget() not available – live refresh disabled.');
                }
                img.onload = null;
            };

            img.src = _buildImageUrl(cfg);

            wrapper.appendChild(img);
            containerEl.appendChild(wrapper);

            options._imgElement = img;
            return img;
        },

        /**
         * Initialise a range widget from a single DOM element's data-* attributes.
         *
         * Reads the following data attributes from the element:
         *   data-doipa      (required)
         *   data-maps       (required) – JSON array string, e.g.
         *                     '[{"minValue":0,"maxValue":2,"image":"/images/test/box.svg"}]'
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
                console.error('[OptergyRange] data-doipa attribute is required on', el);
                return null;
            }

            // Parse maps from data-maps JSON attribute
            var maps = null;
            var mapsAttr = el.getAttribute('data-maps');
            if (mapsAttr) {
                try {
                    maps = JSON.parse(mapsAttr);
                } catch (e) {
                    console.error('[OptergyRange] Could not parse data-maps JSON:', mapsAttr, e);
                    return null;
                }
            }
            if (!maps || !maps.length) {
                console.error('[OptergyRange] data-maps attribute is required (JSON array of {minValue, maxValue, image}).');
                return null;
            }

            var width   = el.getAttribute('data-width');
            var height  = el.getAttribute('data-height');
            var refresh = el.getAttribute('data-refresh');

            return this.create({
                container:      el,
                doipa:          doipa,
                maps:           maps,
                width:          width   !== null ? parseInt(width, 10)   : undefined,
                height:         height  !== null ? parseInt(height, 10)  : undefined,
                refreshSeconds: refresh !== null ? parseInt(refresh, 10) : undefined,
                widgetId:       el.getAttribute('data-widget-id') || undefined,
                title:          el.getAttribute('data-title')     || undefined
            });
        },

        /**
         * Auto-initialise all elements on the page that have the
         * `data-optergy-range` attribute.  Called automatically on
         * DOMContentLoaded, but can also be called manually.
         */
        autoInit: function () {
            var elements = document.querySelectorAll('[data-optergy-range]');
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
         * Initialise a range widget from URL query parameters.
         */
        initFromUrl: function () {
            var params = new URLSearchParams(window.location.search);

            var doipa = params.get('doipa');
            if (!doipa) {
                var errEl = _resolveContainer(params.get('container') || '#rangeContainer');
                if (errEl) {
                    errEl.innerHTML =
                        '<div style="color:#d32f2f;padding:20px;text-align:center;font-size:14px;">' +
                        'Error: <code>doipa</code> parameter is required.<br>' +
                        'Usage: <code>range-widget.html?doipa=300|0|455|85|-1&amp;maps[0].minValue=0&amp;maps[0].maxValue=2&amp;maps[0].image=/images/test/box.svg</code>' +
                        '</div>';
                }
                return null;
            }

            var maps = _parseMapsFromUrl(params);
            if (!maps || !maps.length) {
                var errEl2 = _resolveContainer(params.get('container') || '#rangeContainer');
                if (errEl2) {
                    errEl2.innerHTML =
                        '<div style="color:#d32f2f;padding:20px;text-align:center;font-size:14px;">' +
                        'Error: At least one range map is required.<br>' +
                        'Usage: <code>...&amp;maps[0].minValue=0&amp;maps[0].maxValue=2&amp;maps[0].image=/images/test/box.svg</code>' +
                        '</div>';
                }
                return null;
            }

            return this.create({
                container:      params.get('container')  || '#rangeContainer',
                doipa:          doipa,
                maps:           maps,
                width:          params.has('width')   ? parseInt(params.get('width'), 10)   : undefined,
                height:         params.has('height')  ? parseInt(params.get('height'), 10)  : undefined,
                refreshSeconds: params.has('refresh') ? parseInt(params.get('refresh'), 10) : undefined,
                widgetId:       params.get('widgetId') || undefined,
                title:          params.get('title')    || undefined
            });
        },

        /**
         * Convenience: wire up touch support and standard Optergy page-load
         * sequence.  Call once after creating all widgets.
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
            OptergyRange.autoInit();
        });
    } else {
        // DOM already ready (script loaded dynamically or with defer)
        OptergyRange.autoInit();
    }
}
