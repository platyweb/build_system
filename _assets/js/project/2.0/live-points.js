// Live Points Widget System
// Simplified version based on point-widget.htm for dashboard integration

class LivePointWidget {
    constructor(elementId, bacnetAddress, options = {}) {
        this.elementId = elementId;
        this.bacnetAddress = bacnetAddress;
        this.options = {
            refreshInterval: options.refreshInterval || 10, // seconds
            color: options.color || '#ffffff',
            showAlerts: options.showAlerts || false,
            format: options.format || null // custom formatting function
        };

        this.element = null;
        this.value = 'Loading...';
        this.initialized = false;
    }

    // Parse BACnet address format: deviceInstance|objectType|objectInstance|propertyId|arrayIndex
    parseBacnetAddress() {
        const parts = this.bacnetAddress.split('|');
        if (parts.length >= 4) {
            return {
                deviceInstance: parts[0],
                objectType: parts[1],
                objectInstance: parts[2],
                propertyId: parts[3],
                arrayIndex: parts.length > 4 ? parts[4] : '-1'
            };
        }
        return null;
    }

    // Initialize the widget
    init() {
        this.element = document.getElementById(this.elementId);
        if (!this.element) {
            console.error(`Element with ID "${this.elementId}" not found`);
            return false;
        }

        // Check if Optergy functions are available
        if (typeof assignTextDataWidget === 'undefined') {
            console.error('Optergy libraries not loaded. Please include required scripts.');
            this.element.classList.add('lp-error');
            this.element.textContent = 'Unavailable';
            this.element.setAttribute('title', 'Live data library not loaded');
            return false;
        }

        // Initialize Optergy settings
        if (typeof setRetriesAllowed !== 'undefined') {
            setRetriesAllowed(10);
        }

        // Wrap the element content in a span with _text suffix for Optergy
        const textSpanId = this.elementId + '_text';

        // Check if span already exists
        let textSpan = document.getElementById(textSpanId);
        if (!textSpan) {
            // Create the span and wrap the content
            textSpan = document.createElement('span');
            textSpan.id = textSpanId;
            textSpan.className = 'prompted';
            textSpan.textContent = 'Loading...';

            // Clear element and add span
            this.element.innerHTML = '';
            this.element.appendChild(textSpan);
        }

        // Set up the data widget - note: passing container ID, not the _text ID
        // f=2 requests 2 decimal places from Optergy, sf=1 enables special formatting
        const dataWidgetParams = this.bacnetAddress + '|0&f=2&sf=1';

        try {
            assignTextDataWidget(
                this.elementId,
                dataWidgetParams,
                'false',
                this.options.refreshInterval,
                '',
                this.options.color,
                '', '', '', '', '', '',
                'null'
            );

            this.initialized = true;

            // Apply custom formatting if provided
            if (this.options.format && typeof this.options.format === 'function') {
                this.applyFormatting(textSpanId);
            }

            return true;
        } catch (error) {
            console.error('Error initializing widget:', error);
            this.element.classList.add('lp-error');
            this.element.textContent = 'Unavailable';
            this.element.setAttribute('title', 'Could not initialise live data');
            return false;
        }
    }

    // Apply custom formatting to the displayed value
    applyFormatting(textSpanId) {
        const textSpan = document.getElementById(textSpanId);
        if (!textSpan) return;

        const observer = new MutationObserver(() => {
            const currentValue = textSpan.textContent;
            if (currentValue && currentValue !== 'Loading...' && currentValue !== 'Error') {
                const formattedValue = this.options.format(currentValue);
                if (formattedValue !== currentValue) {
                    // Check if formatted value contains HTML
                    if (formattedValue.includes('<')) {
                        textSpan.innerHTML = formattedValue;
                    } else {
                        textSpan.textContent = formattedValue;
                    }
                }
            }
        });

        observer.observe(textSpan, {
            childList: true,
            characterData: true,
            subtree: true
        });
    }

    // Refresh the widget value
    refresh() {
        if (typeof refreshPoint !== 'undefined') {
            refreshPoint(this.elementId);
        }
    }
}

// ─── Format Configuration ────────────────────────────────────────────────────
// Maps named format types to their display properties.
// Each entry defines: unit, unitPosition, useThousands, showSign.
// New formats can be added here without touching formatter logic.
// Callers can also bypass named formats entirely by specifying
// data-unit, data-unit-position, data-thousands, data-show-sign attributes directly.
const FORMAT_CONFIG = {
    temperature:        { unit: '°C',  unitPosition: 'after',  useThousands: false, showSign: false },
    percentage:         { unit: '%',   unitPosition: 'after',  useThousands: false, showSign: false },
    percentage_signed:  { unit: '%',   unitPosition: 'after',  useThousands: false, showSign: true  },
    nabers:             { unit: '★',   unitPosition: 'after',  useThousands: false, showSign: false },
    power:              { unit: 'kW',  unitPosition: 'after',  useThousands: true,  showSign: false },
    energy:             { unit: 'kWh', unitPosition: 'after',  useThousands: true,  showSign: false },
    water:              { unit: 'm³',  unitPosition: 'after',  useThousands: true,  showSign: false },
    gas:                { unit: 'm³',  unitPosition: 'after',  useThousands: true,  showSign: false },
    weight:             { unit: 't',   unitPosition: 'after',  useThousands: true,  showSign: false },
    voltage:            { unit: 'V',   unitPosition: 'after',  useThousands: true,  showSign: false },
    current:            { unit: 'A',   unitPosition: 'after',  useThousands: true,  showSign: false },
    number:             { unit: '',    unitPosition: 'after',  useThousands: true,  showSign: false },
    electariff:         { unit: 'p/kWh',    unitPosition: 'after',  useThousands: true,  showSign: false },
    cost:               { unit: '£',   unitPosition: 'before', useThousands: true,  showSign: false }
};

// ─── Unified Numeric Formatter ───────────────────────────────────────────────
// Single formatter that handles all numeric format types based on config params.
function createNumericFormatter({ unit, unitPosition, useThousands, showSign, decimals, preText, postText }) {
    return function(value) {
        // Skip if already formatted (check unit is present in value)
        if (unit && typeof value === 'string' && value.includes(unit)) return value;

        // Clean and parse
        const cleanValue = String(value).replace(/,/g, '').replace(/[^\d.-]/g, '');
        const numValue = parseFloat(cleanValue);
        if (isNaN(numValue)) return value;

        // Format number
        let formatted = numValue.toFixed(decimals);

        // Apply thousand separators
        if (useThousands) {
            const parts = formatted.split('.');
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            formatted = parts.join('.');
        }

        // Apply sign prefix
        const sign = (showSign && numValue > 0) ? '+' : '';

        // Build output: preText + [unitBefore] + sign + number + [unitAfter] + postText
        const unitBefore = (unitPosition === 'before' && unit) ? unit : '';
        const unitAfter  = (unitPosition !== 'before' && unit) ? ' ' + unit : '';

        return preText + unitBefore + sign + formatted + unitAfter + postText;
    };
}

// Dashboard Live Points Manager
const DashboardLivePoints = {
    widgets: {},

    // Initialize a single live point
    init: function(elementId, bacnetAddress, options = {}) {
        const widget = new LivePointWidget(elementId, bacnetAddress, options);
        const success = widget.init();

        if (success) {
            this.widgets[elementId] = widget;
        }

        return widget;
    },

    // Initialize multiple live points from configuration
    initFromConfig: function(config) {
        const results = {};

        for (const [key, value] of Object.entries(config)) {
            results[key] = this.init(value.elementId, value.bacnetAddress, value.options || {});
        }

        return results;
    },

    // Refresh all widgets
    refreshAll: function() {
        for (const widget of Object.values(this.widgets)) {
            widget.refresh();
        }
    },

    // Get widget by element ID
    get: function(elementId) {
        return this.widgets[elementId] || null;
    }
};

// ─── Context Menu System ─────────────────────────────────────────────────────
// Right-click context menu for live point elements, matching Optergy backend pattern.
// Opt-in only: add data-context-menu="item1,item2,..." to enable on a specific element.
//
// Available menu item keys:
//   refresh          – Refresh the live point value
//   change-value     – Open Optergy override dialog to change the BACnet point
//   add-trendlog     – Open the Add Trendlog dialog for this point
//   add-alarm        – Open the Add Alarm dialog for this point
//   view-activity    – Open the Point Override Report for this point
//   device-properties – Open the Device Properties page
//
// Use "all" as a shorthand for every item.
//
// Example HTML usage:
//   <div id="live-temp" data-bacnet="10010|0|0|85|-1" data-format="temperature"
//        data-context-menu="refresh,change-value,add-trendlog">Loading...</div>
//
//   <div id="live-demand" data-bacnet="300|0|19682|85|-1" data-format="power"
//        data-context-menu="all">Loading...</div>

const LivePointContextMenu = {
    _menuCounter: 0,
    _initialized: false,

    // All recognised menu-item keys (in display order)
    ALL_ITEMS: [
        'refresh',
        'change-value',
        'add-trendlog',
        'add-alarm',
        'view-activity',
        'device-properties'
    ],

    // Groups for inserting separators between logical sections
    _groups: [
        ['refresh'],
        ['change-value'],
        ['add-trendlog', 'add-alarm'],
        ['view-activity', 'device-properties']
    ],

    // Inject required CSS styles for the context menu
    _injectStyles: function() {
        if (document.getElementById('lp-context-menu-styles')) return;
        var style = document.createElement('style');
        style.id = 'lp-context-menu-styles';
        style.textContent =
            'div.lp-contextMenu {' +
            '  background-color: #1e1e2d;' +
            '  border: 1px solid rgba(255,255,255,0.12);' +
            '  border-radius: 6px;' +
            '  box-shadow: 0 8px 24px rgba(0,0,0,0.45);' +
            '  z-index: 100000000;' +
            '  top: 0px;' +
            '  left: 0px;' +
            '  font-weight: normal;' +
            '  position: absolute;' +
            '  min-width: 180px;' +
            '  max-width: 600px;' +
            '  padding: 4px 0;' +
            '  display: none;' +
            '}' +
            '.lp-menuItem {' +
            '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;' +
            '  font-size: 13px;' +
            '  background-color: transparent;' +
            '  color: #c3c3e0;' +
            '  width: auto;' +
            '  cursor: default;' +
            '  padding: 7px 14px;' +
            '  margin: 0;' +
            '  border: none;' +
            '  white-space: nowrap;' +
            '  display: flex;' +
            '  align-items: center;' +
            '  gap: 8px;' +
            '}' +
            '.lp-menuItem:hover, .lp-highlightedMenuItem {' +
            '  background-color: rgba(80, 120, 200, 0.25);' +
            '  color: #7da4f5;' +
            '}' +
            '.lp-menuItem .lp-menu-icon {' +
            '  width: 16px;' +
            '  text-align: center;' +
            '  font-size: 14px;' +
            '  opacity: 0.7;' +
            '}' +
            '.lp-menuSeparator {' +
            '  height: 1px;' +
            '  background: rgba(255,255,255,0.08);' +
            '  margin: 4px 10px;' +
            '}';
        document.head.appendChild(style);
    },

    // Create required DOM infrastructure
    _createInfrastructure: function() {
        if (document.getElementById('lp-menu')) return;
        var menu = document.createElement('div');
        menu.id = 'lp-menu';
        menu.className = 'lp-contextMenu';
        document.body.appendChild(menu);
    },

    // Parse BACnet address into components
    _parseBacnet: function(bacnetAddress) {
        var parts = bacnetAddress.split('|');
        if (parts.length >= 4) {
            return {
                deviceInstance: parts[0],
                objectType: parts[1],
                objectInstance: parts[2],
                propertyId: parts[3],
                arrayIndex: parts.length > 4 ? parts[4] : '-1',
                full: bacnetAddress
            };
        }
        return null;
    },

    // Parse the data-context-menu attribute into an array of enabled item keys
    _parseEnabledItems: function(attr) {
        if (!attr) return [];
        var trimmed = attr.trim().toLowerCase();
        if (trimmed === 'all') return this.ALL_ITEMS.slice();
        return trimmed.split(/[\s,|]+/).filter(function(k) { return k.length > 0; });
    },

    // Build a single menu item HTML string
    _menuItemHTML: function(icon, label, onclick) {
        return '<div class="lp-menuItem" ' +
            'onmouseover="this.classList.add(\'lp-highlightedMenuItem\')" ' +
            'onmouseout="this.classList.remove(\'lp-highlightedMenuItem\')" ' +
            'onclick="' + onclick + '">' +
            '<span class="lp-menu-icon">' + icon + '</span>' +
            '<span>' + label + '</span>' +
            '</div>';
    },

    // Registry of all available menu items.  Each returns an HTML string or '' if unavailable.
    _itemBuilders: {
        'refresh': function(ctx, el, parsed) {
            var textSpanId = el.id + '_text';
            return ctx._menuItemHTML(
                '&#x21bb;', 'Refresh',
                "LivePointContextMenu._refreshPoint('" + textSpanId + "'); LivePointContextMenu._hide();"
            );
        },
        'change-value': function(ctx, el, parsed) {
            var textSpanId = el.id + '_text';
            return ctx._menuItemHTML(
                '&#x270E;', 'Change Value',
                "LivePointContextMenu._overridePoint('" + el.id + "', '" + textSpanId + "', '" + parsed.full + "'); LivePointContextMenu._hide();"
            );
        },
        'add-trendlog': function(ctx, el, parsed) {
            return ctx._menuItemHTML(
                '&#x1F4C8;', 'Add Trendlog',
                "window.open('/trendlogs/?loadWithDialog&doipa=" + encodeURIComponent(parsed.full) + "'); LivePointContextMenu._hide();"
            );
        },
        'add-alarm': function(ctx, el, parsed) {
            return ctx._menuItemHTML(
                '&#x1F514;', 'Add Alarm',
                "window.open('/bacnetAlarms/?loadWithDialog&doipa=" + encodeURIComponent(parsed.full) + "', 'Bacnet Alarms'); LivePointContextMenu._hide();"
            );
        },
        'view-activity': function(ctx, el, parsed) {
            var url = '/userActivity/PointOverrideReport.html?'
                + 'filters[0].deviceInstance=' + parsed.deviceInstance
                + '&filters[0].objectType=' + parsed.objectType
                + '&filters[0].objectInstance=' + parsed.objectInstance
                + '&popup=true';
            return ctx._menuItemHTML(
                '&#x1F4CB;', 'View Change Activity',
                "window.open('" + url + "'); LivePointContextMenu._hide();"
            );
        },
        'device-properties': function(ctx, el, parsed) {
            return ctx._menuItemHTML(
                '&#x2699;', 'Device Properties',
                "window.open('page?d=OptergyTemplates/DeviceTemplates/99999999&device=" + parsed.deviceInstance + "'); LivePointContextMenu._hide();"
            );
        }
    },

    // Build the context menu HTML for a given element, filtered to enabled items
    _buildMenu: function(element, enabledItems) {
        var bacnetAddress = element.getAttribute('data-bacnet');
        var parsed = this._parseBacnet(bacnetAddress);
        if (!parsed) return '';

        var self = this;
        var html = '';
        var renderedGroups = [];

        // Walk through groups in order; only include groups that have at least one enabled item
        this._groups.forEach(function(group) {
            var groupHtml = '';
            group.forEach(function(key) {
                if (enabledItems.indexOf(key) !== -1 && self._itemBuilders[key]) {
                    groupHtml += self._itemBuilders[key](self, element, parsed);
                }
            });
            if (groupHtml) {
                renderedGroups.push(groupHtml);
            }
        });

        // Join groups with separators
        for (var i = 0; i < renderedGroups.length; i++) {
            if (i > 0) html += '<div class="lp-menuSeparator"></div>';
            html += renderedGroups[i];
        }

        return html;
    },

    // Show the context menu at the mouse position
    _show: function(e, element, enabledItems) {
        var menu = document.getElementById('lp-menu');
        if (!menu) return false;

        var html = this._buildMenu(element, enabledItems);
        if (!html) return false;

        menu.innerHTML = html;

        // Position the menu
        var left = e.pageX;
        var top = e.pageY;

        // Temporarily show off-screen to measure
        menu.style.left = '-9999px';
        menu.style.top = '-9999px';
        menu.style.display = 'block';
        var menuWidth = menu.offsetWidth;
        var menuHeight = menu.offsetHeight;

        var viewW = document.documentElement.clientWidth + window.scrollX;
        var viewH = document.documentElement.clientHeight + window.scrollY;

        if (left + menuWidth > viewW) left = left - menuWidth;
        if (top + menuHeight > viewH)  top  = top  - menuHeight;
        if (left < 0) left = 0;
        if (top  < 0) top  = 0;

        menu.style.left = left + 'px';
        menu.style.top  = top  + 'px';
        menu.style.display = 'block';

        return false;
    },

    // Hide the context menu
    _hide: function() {
        var menu = document.getElementById('lp-menu');
        if (menu) {
            menu.style.display = 'none';
            menu.innerHTML = '';
        }
    },

    // Refresh a point value
    _refreshPoint: function(textSpanId) {
        if (typeof refreshPoint !== 'undefined') {
            refreshPoint(textSpanId);
        }
    },

    // Preload Optergy dialog CSS/JS dependencies (needed for override/change-value).
    // Must be called early (at init time) so assets are ready before user clicks.
    _optergyDepsLoaded: false,
    _preloadOptergyDeps: function() {
        if (this._optergyDepsLoaded) return;
        this._optergyDepsLoaded = true;

        // Global variables expected by Optergy override form scripts
        if (typeof window.subDevice === 'undefined') window.subDevice = -1;
        if (typeof window.subObject === 'undefined') window.subObject = -1;
        if (typeof window.subInstance === 'undefined') window.subInstance = -1;

        // Required CSS
        var cssFiles = [
            '/css/optergy-form-dialog.css',
            '/css/jquery-optergy.css',
            '/css/keyboard.css'
        ];
        cssFiles.forEach(function(href) {
            if (!document.querySelector('link[href*="' + href.replace('/css/', '') + '"]')) {
                var link = document.createElement('link');
                link.rel = 'stylesheet';
                link.type = 'text/css';
                link.media = 'all';
                link.href = href;
                document.head.appendChild(link);
            }
        });

        // Required JS
        var jsFiles = [
            '/js/jquery.keyboard.js',
            '/js/widget-ui.spinner.js'
        ];
        jsFiles.forEach(function(src) {
            var baseName = src.split('/').pop().replace('.js', '');
            if (!document.querySelector('script[src*="' + baseName + '"]')) {
                var script = document.createElement('script');
                script.type = 'text/javascript';
                script.src = src;
                document.head.appendChild(script);
            }
        });
    },

    // ── Override / Change Value ───────────────────────────────────────
    // The native Optergy override() function requires a compiled display
    // file path and a point hash to save changes via XMLUpdateListener.
    //
    // To make a point overridable on a custom dashboard:
    //   1.  Add the BACnet point to the Optergy display referenced by
    //       OVERRIDE_FILE below, via the Display Tool, and recompile.
    //   2.  Right-click the point in the compiled display → Change Value
    //       and capture the "ph" value from the XMLUpdateListener POST
    //       in the Network tab of DevTools.
    //   3.  On your HTML element, add:
    //         data-override-hash="<ph value from step 2>"
    //         data-context-menu="change-value"

    // Default Optergy display file used for all overrides.
    // All overridable points must exist in this compiled display.
    OVERRIDE_FILE: '/usr/local/Optergy/Displays//tlb/test.xml',

    // Override/change a point value.
    _overridePoint: function(elementId, textSpanId, bacnetAddress) {
        if (typeof override !== 'undefined') {
            var el = document.getElementById(elementId);
            var file = (el && el.getAttribute('data-override-file')) || this.OVERRIDE_FILE;
            var hash = (el && el.getAttribute('data-override-hash')) || '';

            if (!hash) {
                console.warn(
                    'Override for ' + elementId + ' (' + bacnetAddress + '): missing ' +
                    'data-override-hash attribute.'
                );
            }

            override(file, hash, textSpanId, bacnetAddress, null, 'Inactive', null);
        } else {
            console.warn('Override function not available. Optergy forms library may not be loaded.');
        }
    },

    // Initialize — only attaches to elements that have data-context-menu attribute
    init: function() {
        if (this._initialized) return;
        this._initialized = true;

        var self = this;

        // Only proceed if there are any opt-in elements
        var elements = document.querySelectorAll('[data-bacnet][data-context-menu]');
        if (elements.length === 0) return;

        this._injectStyles();
        this._createInfrastructure();

        // Close menu on left-click anywhere
        document.addEventListener('click', function() {
            self._hide();
        });

        // Close menu on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') self._hide();
        });

        // Check if any element needs change-value (preload Optergy deps early)
        var needsOverrideDeps = false;

        // Attach context menu to each opted-in element
        elements.forEach(function(element) {
            var enabledItems = self._parseEnabledItems(element.getAttribute('data-context-menu'));
            if (enabledItems.length === 0) return;

            if (enabledItems.indexOf('change-value') !== -1) {
                needsOverrideDeps = true;
            }

            element.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                e.stopPropagation();
                self._show(e, element, enabledItems);
                return false;
            });

            // Visual hint: cursor + persistent glyph so the menu is discoverable
            element.style.cursor = 'context-menu';
            element.classList.add('lp-has-menu');
            if (!element.getAttribute('title')) {
                element.setAttribute('title', 'Right-click for actions');
            }
        });

        // Preload Optergy override dependencies only on pages
        // that actually have change-value menu items
        if (needsOverrideDeps) {
            this._preloadOptergyDeps();
        }

        // Prevent default browser context menu on the menu itself
        var menu = document.getElementById('lp-menu');
        if (menu) {
            menu.addEventListener('contextmenu', function(e) {
                e.preventDefault();
            });
        }
    }
};


// ─── Data Freshness Tracker ──────────────────────────────────────────────────
// The Optergy library writes values into each point's `_text` span but gives us
// no update callback. We observe that span: any real value stamps a timestamp.
// A periodic sweep then flags points that have gone stale (no update for 3× their
// refresh interval) or never arrived at all, and surfaces "updated Xs ago" as a
// tooltip. Visual states are styled via .lp-loading / .lp-stale / .lp-error.
const LivePointFreshness = {
    tracked: [],
    STALE_MULTIPLIER: 3,
    MIN_STALE_MS: 30000,   // never flag stale sooner than 30s
    LOAD_GRACE_MS: 20000,  // allow 20s for the first value before "no data"
    SWEEP_MS: 5000,
    _started: false,

    // A point counts as "having a value" once its span holds an element node
    // (status icons) or non-placeholder text.
    _hasValue: function (span) {
        if (!span) return false;
        for (var i = 0; i < span.childNodes.length; i++) {
            if (span.childNodes[i].nodeType === 1) return true; // <img>/<span> = rendered
        }
        var t = (span.textContent || '').trim();
        return t !== '' && t !== 'Loading...' && !/^(error|unavailable)$/i.test(t);
    },

    _relTime: function (ms) {
        var s = Math.round(ms / 1000);
        if (s < 60) return s + 's';
        var m = Math.round(s / 60);
        if (m < 60) return m + 'm';
        return Math.round(m / 60) + 'h';
    },

    // ── Threshold / alert colouring ──────────────────────────────────────
    // Opt-in via attributes on the live element:
    //   data-warn-above / data-danger-above   → flag when value >= threshold
    //   data-warn-below / data-danger-below    → flag when value <= threshold
    // e.g. a power factor cell: data-warn-below="0.95" data-danger-below="0.9".
    // Adds .lp-warn (amber) or .lp-danger (red); danger wins.
    _num: function (text) {
        var cleaned = String(text || '').replace(/,/g, '').replace(/[^0-9.\-]/g, '');
        return parseFloat(cleaned);
    },

    evaluateThresholds: function (element, span) {
        var da = element.getAttribute('data-danger-above');
        var wa = element.getAttribute('data-warn-above');
        var db = element.getAttribute('data-danger-below');
        var wb = element.getAttribute('data-warn-below');
        if (da === null && wa === null && db === null && wb === null) return;

        var v = this._num(span.textContent);
        element.classList.remove('lp-warn', 'lp-danger');
        if (isNaN(v)) return;

        if ((da !== null && v >= parseFloat(da)) || (db !== null && v <= parseFloat(db))) {
            element.classList.add('lp-danger');
        } else if ((wa !== null && v >= parseFloat(wa)) || (wb !== null && v <= parseFloat(wb))) {
            element.classList.add('lp-warn');
        }
    },

    register: function (element, refreshSec) {
        if (!element) return;
        var span = document.getElementById(element.id + '_text') || element;
        var rec = {
            el: element,
            span: span,
            refreshMs: (parseInt(refreshSec, 10) || 10) * 1000,
            lastUpdate: 0,
            started: Date.now()
        };
        this.tracked.push(rec);
        if (!element.classList.contains('lp-error')) element.classList.add('lp-loading');

        var self = this;
        var observer = new MutationObserver(function () {
            if (!self._hasValue(span)) return;
            rec.lastUpdate = Date.now();
            element.classList.remove('lp-loading', 'lp-stale', 'lp-error');
            element.setAttribute('title', 'Updated just now');
            self.evaluateThresholds(element, span);
        });
        observer.observe(span, { childList: true, characterData: true, subtree: true });

        // Value may already be present by the time we register.
        if (this._hasValue(span)) {
            rec.lastUpdate = Date.now();
            element.classList.remove('lp-loading');
        }
    },

    sweep: function () {
        var now = Date.now();
        var self = this;
        this.tracked.forEach(function (rec) {
            var el = rec.el;
            if (rec.lastUpdate) {
                var age = now - rec.lastUpdate;
                el.setAttribute('title', 'Updated ' + self._relTime(age) + ' ago');
                var staleAfter = Math.max(rec.refreshMs * self.STALE_MULTIPLIER, self.MIN_STALE_MS);
                if (age > staleAfter) el.classList.add('lp-stale');
                else el.classList.remove('lp-stale');
            } else if (now - rec.started > self.LOAD_GRACE_MS) {
                el.classList.remove('lp-loading');
                el.classList.add('lp-error');
                el.setAttribute('title', 'No data — point unavailable');
            }
        });
    },

    start: function () {
        if (this._started) return;
        this._started = true;
        var self = this;
        setInterval(function () { self.sweep(); }, this.SWEEP_MS);
    }
};

// Auto-initialize widgets with data-bacnet attribute when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit to ensure Optergy libraries are loaded
    setTimeout(function() {
        const elements = document.querySelectorAll('[data-bacnet]');

        elements.forEach(function(element) {
            const bacnetAddress = element.getAttribute('data-bacnet');
            const refreshInterval = element.getAttribute('data-refresh') || 10;
            const format = element.getAttribute('data-format');
            const decimalPlaces = element.getAttribute('data-decimal-places');
            const decimals = decimalPlaces !== null ? parseInt(decimalPlaces) : 1; // Default to 1 decimal
            const preText = element.getAttribute('data-pre-text') || '';
            const postText = element.getAttribute('data-post-text') || '';

            if (bacnetAddress) {
                const options = {
                    refreshInterval: parseInt(refreshInterval),
                    color: element.style.color || '#ffffff',
                    preText: preText,
                    postText: postText,
                    // Get custom SVG paths if specified
                    statusOnlineSvg: element.getAttribute('data-status-online-svg'),
                    statusOfflineSvg: element.getAttribute('data-status-offline-svg'),
                    statusOnlineText: element.getAttribute('data-status-online-text') || 'Online',
                    statusOfflineText: element.getAttribute('data-status-offline-text') || 'Offline'
                };

                // Add custom formatting if specified
                if (format) {
                    if (format === 'status' || format === 'boolean') {
                        // Status/boolean is a special case — renders HTML with icons
                        const onlineSvg = options.statusOnlineSvg;
                        const offlineSvg = options.statusOfflineSvg;
                        const onlineText = options.statusOnlineText;
                        const offlineText = options.statusOfflineText;

                        options.format = function(value) {
                            const numValue = parseFloat(value);
                            if (isNaN(numValue)) return value;

                            const isOk = numValue === 1;
                            const color = isOk ? '#4caf50' : '#f44336';
                            const text = isOk ? onlineText : offlineText;

                            let iconHtml;
                            if (isOk && onlineSvg) {
                                iconHtml = `<img src="${onlineSvg}" style="width: 24px; height: 24px; vertical-align: middle; margin-right: 8px;" alt="Online">`;
                            } else if (!isOk && offlineSvg) {
                                iconHtml = `<img src="${offlineSvg}" style="width: 24px; height: 24px; vertical-align: middle; margin-right: 8px;" alt="Offline">`;
                            } else {
                                iconHtml = `<span style="color: ${color}; font-size: 32px; vertical-align: middle; line-height: 1; margin-right: 4px;">●</span>`;
                            }

                            return preText + `${iconHtml}<span style="color: ${color};">${text}</span>` + postText;
                        };
                    } else {
                        // ── Unified numeric formatting ──────────────────────────
                        // Resolve config: use named format lookup, then allow
                        // per-element data-* attributes to override any property.
                        const baseConfig = FORMAT_CONFIG[format] || FORMAT_CONFIG['number'];

                        // Per-element attribute overrides (these take priority)
                        const attrUnit         = element.getAttribute('data-unit');
                        const attrUnitPosition = element.getAttribute('data-unit-position');
                        const attrThousands    = element.getAttribute('data-thousands');
                        const attrShowSign     = element.getAttribute('data-show-sign');

                        options.format = createNumericFormatter({
                            unit:          attrUnit         !== null ? attrUnit                       : baseConfig.unit,
                            unitPosition:  attrUnitPosition !== null ? attrUnitPosition               : baseConfig.unitPosition,
                            useThousands:  attrThousands    !== null ? attrThousands === 'true'       : baseConfig.useThousands,
                            showSign:      attrShowSign     !== null ? attrShowSign  === 'true'       : baseConfig.showSign,
                            decimals:      decimals,
                            preText:       preText,
                            postText:      postText
                        });
                    }
                }

                DashboardLivePoints.init(element.id, bacnetAddress, options);
                LivePointFreshness.register(element, refreshInterval);
            }
        });

        // Initialize context menus after all widgets are set up
        LivePointContextMenu.init();

        // Begin freshness / stale monitoring once all widgets are registered
        LivePointFreshness.start();
    }, 500);
});
