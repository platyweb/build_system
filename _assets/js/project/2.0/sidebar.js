// Sidebar behaviour. sidebar-template.js loads this once it has put the
// sidebar's markup in the page.
//   - A sub-menu slides open and shut when its item is clicked.
//   - The collapse button (#btn-collapse) shrinks the sidebar to its icons;
//     each top-level sub-menu then opens as a pop-out beside its item.
//   - The toggle button (#btn-toggle) and the overlay show and hide the
//     sidebar on narrow screens.
//
// It replaces the pro-sidebar template's webpack bundle (MIT), most of which
// was Popper 2 (MIT), there only to place the pop-outs. placePopOut() places
// them as Popper did with the template's options (placement 'right',
// strategy 'fixed', flipping to 'left', computeStyles adaptive: false): the
// steps below are Popper's, cut down to that case. It assumes no ancestor of
// the sidebar has a transform, so a fixed pop-out sits in viewport
// coordinates. A pop-out is only placed while the sidebar is collapsed; when
// it's expanded, the CSS lays sub-menus out in the menu.

(function () {
    'use strict';

    var ANIMATION_DURATION = 300;
    var SIDEBAR_EL = document.getElementById('sidebar');
    var SUB_MENU_ELS = document.querySelectorAll('.menu > ul > .menu-item.sub-menu');
    var FIRST_SUB_MENUS_BTN = document.querySelectorAll('.menu > ul > .menu-item.sub-menu > a');
    var INNER_SUB_MENUS_BTN = document.querySelectorAll('.menu > ul > .menu-item.sub-menu .menu-item.sub-menu > a');

    function isCollapsed() {
        return SIDEBAR_EL.classList.contains('collapsed');
    }

    // ─── Sliding a sub-menu open and shut ────────────────────────────────────

    function slideUp(target, duration) {
        if (duration === undefined) duration = ANIMATION_DURATION;
        target.parentElement.classList.remove('open');
        target.style.transitionProperty = 'height, margin, padding';
        target.style.transitionDuration = duration + 'ms';
        target.style.boxSizing = 'border-box';
        target.style.height = target.offsetHeight + 'px';
        target.offsetHeight; // forces a reflow
        target.style.overflow = 'hidden';
        target.style.height = 0;
        target.style.paddingTop = 0;
        target.style.paddingBottom = 0;
        target.style.marginTop = 0;
        target.style.marginBottom = 0;
        window.setTimeout(function () {
            target.style.display = 'none';
            target.style.removeProperty('height');
            target.style.removeProperty('padding-top');
            target.style.removeProperty('padding-bottom');
            target.style.removeProperty('margin-top');
            target.style.removeProperty('margin-bottom');
            target.style.removeProperty('overflow');
            target.style.removeProperty('transition-duration');
            target.style.removeProperty('transition-property');
        }, duration);
    }

    function slideDown(target, duration) {
        if (duration === undefined) duration = ANIMATION_DURATION;
        target.parentElement.classList.add('open');
        target.style.removeProperty('display');
        var display = window.getComputedStyle(target).display;
        if (display === 'none') display = 'block';
        target.style.display = display;
        var height = target.offsetHeight;
        target.style.overflow = 'hidden';
        target.style.height = 0;
        target.style.paddingTop = 0;
        target.style.paddingBottom = 0;
        target.style.marginTop = 0;
        target.style.marginBottom = 0;
        target.offsetHeight; // forces a reflow
        target.style.boxSizing = 'border-box';
        target.style.transitionProperty = 'height, margin, padding';
        target.style.transitionDuration = duration + 'ms';
        target.style.height = height + 'px';
        target.style.removeProperty('padding-top');
        target.style.removeProperty('padding-bottom');
        target.style.removeProperty('margin-top');
        target.style.removeProperty('margin-bottom');
        window.setTimeout(function () {
            target.style.removeProperty('height');
            target.style.removeProperty('overflow');
            target.style.removeProperty('transition-duration');
            target.style.removeProperty('transition-property');
        }, duration);
    }

    function slideToggle(target, duration) {
        if (window.getComputedStyle(target).display === 'none') return slideDown(target, duration);
        return slideUp(target, duration);
    }

    // ─── Pop-outs (collapsed sidebar) ────────────────────────────────────────

    // Each top-level sub-menu item and its list, the pop-out.
    var popOuts = Array.prototype.map.call(SUB_MENU_ELS, function (item) {
        return { reference: item, popper: item.lastElementChild };
    });

    // What Popper set on each pop-out at the start and on every update; while
    // the sidebar is expanded, the CSS overrides it.
    var POP_OUT_STYLE = { position: 'fixed', left: '0', top: '0', margin: '0' };

    // The preferred placement, then flip's fallbacks, in the order flip tries them.
    var PLACEMENTS = ['right', 'left', 'right'];
    var OPPOSITE = { top: 'bottom', bottom: 'top' };

    // getLayoutRect's size: the layout size, unless the drawn size is within 1px of it.
    function layoutSize(el) {
        var drawn = el.getBoundingClientRect();
        var width = el.offsetWidth;
        var height = el.offsetHeight;
        if (Math.abs(drawn.width - width) <= 1) width = drawn.width;
        if (Math.abs(drawn.height - height) <= 1) height = drawn.height;
        return { width: width, height: height };
    }

    // getViewportRect: the visual viewport, where the browser has one.
    function viewportRect() {
        var html = document.documentElement;
        var vv = window.visualViewport;
        var width = html.clientWidth;
        var height = html.clientHeight;
        var x = 0;
        var y = 0;
        if (vv) {
            width = vv.width;
            height = vv.height;
            if (!/^((?!chrome|android).)*safari/i.test(navigator.userAgent)) {
                x = vv.offsetLeft;
                y = vv.offsetTop;
            }
        }
        x += html.getBoundingClientRect().left + window.pageXOffset;
        return { top: y, left: x, bottom: y + height, right: x + width };
    }

    // computeOffsets: beside the item, centred on it.
    function offsetsFor(placement, ref, pop) {
        return {
            x: placement === 'right' ? ref.x + ref.width : ref.x - pop.width,
            y: ref.y + ref.height / 2 - pop.height / 2
        };
    }

    // detectOverflow: how far the pop-out, at `placement`, overflows each side
    // of the viewport (positive = overflowing).
    function overflowAt(placement, ref, pop, clip) {
        var at = offsetsFor(placement, ref, pop);
        return {
            top: clip.top - at.y,
            bottom: at.y + pop.height - clip.bottom,
            left: clip.left - at.x,
            right: at.x + pop.width - clip.right
        };
    }

    // flip (mainAxis, altAxis and flipVariations on): the first placement that
    // fits on every side checked; failing that, the first that fits on fewer.
    function flip(ref, pop, clip) {
        var checksByPlacement = {};
        var i;
        for (i = 0; i < PLACEMENTS.length; i++) {
            var placement = PLACEMENTS[i];
            var overflow = overflowAt(placement, ref, pop, clip);
            var mainVariationSide = ref.height > pop.height ? 'bottom' : 'top';
            var checks = [overflow[placement] <= 0, overflow[mainVariationSide] <= 0,
                          overflow[OPPOSITE[mainVariationSide]] <= 0];
            if (checks[0] && checks[1] && checks[2]) return placement;
            checksByPlacement[placement] = checks;
        }
        for (var n = 3; n > 0; n--) {
            for (i = 0; i < PLACEMENTS.length; i++) {
                if (checksByPlacement[PLACEMENTS[i]].slice(0, n).every(Boolean)) return PLACEMENTS[i];
            }
        }
        return PLACEMENTS[0];
    }

    // preventOverflow (main axis only, tethered): slide the pop-out up or down
    // to keep it in the viewport, but never off its item.
    function preventOverflow(placement, at, ref, pop, clip) {
        var overflow = overflowAt(placement, ref, pop, clip);
        var min = at.y + overflow.top;
        var max = at.y - overflow.bottom;
        var tetherMin = at.y + ref.height / 2 + pop.height / 2;
        var tetherMax = at.y - ref.height / 2 - pop.height / 2;
        at.y = Math.max(Math.min(min, tetherMin), Math.min(at.y, Math.max(max, tetherMax)));
    }

    // computeStyles' rounding to the device pixel grid.
    function roundByDPR(v) {
        var dpr = window.devicePixelRatio || 1;
        return Math.round(Math.round(v * dpr) / dpr) || 0;
    }

    function placePopOut(popOut) {
        var r = popOut.reference.getBoundingClientRect();
        var ref = { x: r.left, y: r.top, width: r.width, height: r.height };
        var pop = layoutSize(popOut.popper);
        var clip = viewportRect();
        var placement = flip(ref, pop, clip);
        var at = offsetsFor(placement, ref, pop);
        preventOverflow(placement, at, ref, pop, clip);
        var x = roundByDPR(at.x);
        var y = roundByDPR(at.y);
        Object.assign(popOut.popper.style, POP_OUT_STYLE, {
            transform: (window.devicePixelRatio || 1) < 2
                ? 'translate(' + x + 'px, ' + y + 'px)'
                : 'translate3d(' + x + 'px, ' + y + 'px, 0)'
        });
        popOut.popper.setAttribute('data-popper-placement', placement);
    }

    function updatePopOuts() {
        var collapsed = isCollapsed();
        popOuts.forEach(function (popOut) {
            if (collapsed) placePopOut(popOut);
            else Object.assign(popOut.popper.style, POP_OUT_STYLE);
        });
    }

    function hidePopOut(popOut) {
        popOut.popper.style.visibility = 'hidden';
    }

    function closePopOuts() {
        popOuts.forEach(hidePopOut);
    }

    function togglePopOut(target) {
        if (window.getComputedStyle(target).visibility === 'hidden') target.style.visibility = 'visible';
        else target.style.visibility = 'hidden';
    }

    popOuts.forEach(function (popOut) {
        Object.assign(popOut.popper.style, POP_OUT_STYLE);
    });
    closePopOuts();

    // A click outside a pop-out and its item closes it.
    document.addEventListener('click', function (e) {
        popOuts.forEach(function (popOut) {
            if (isCollapsed() && !popOut.popper.contains(e.target) && !popOut.reference.contains(e.target)) {
                hidePopOut(popOut);
            }
        });
    }, false);

    // Follow the items as the page scrolls or resizes, and a pop-out as it
    // changes size (an inner sub-menu sliding open inside it).
    window.addEventListener('scroll', updatePopOuts, { capture: true, passive: true });
    window.addEventListener('resize', updatePopOuts, { passive: true });
    if (window.visualViewport) window.visualViewport.addEventListener('scroll', updatePopOuts, { passive: true });
    if (window.ResizeObserver) {
        var observer = new ResizeObserver(updatePopOuts);
        popOuts.forEach(function (popOut) {
            observer.observe(popOut.popper);
            observer.observe(popOut.reference);
        });
    }

    // Once the sidebar's width animation is over, place the pop-outs again.
    function updatePopOutsAfterAnimation() {
        setTimeout(function () {
            popOuts.forEach(function (popOut) {
                popOut.popper.style.display = 'none';
            });
            updatePopOuts();
        }, ANIMATION_DURATION);
    }

    // ─── Buttons and menu items ──────────────────────────────────────────────

    document.getElementById('btn-collapse').addEventListener('click', function () {
        SIDEBAR_EL.classList.toggle('collapsed');
        closePopOuts();
        if (isCollapsed()) {
            FIRST_SUB_MENUS_BTN.forEach(function (element) {
                element.parentElement.classList.remove('open');
            });
        }
        updatePopOutsAfterAnimation();
    });

    // Narrow screens: show or hide the sidebar.
    document.getElementById('btn-toggle').addEventListener('click', function () {
        SIDEBAR_EL.classList.toggle('toggled');
        updatePopOutsAfterAnimation();
    });

    document.getElementById('overlay').addEventListener('click', function () {
        SIDEBAR_EL.classList.toggle('toggled');
    });

    document.querySelectorAll('.menu-item.sub-menu.open').forEach(function (element) {
        element.lastElementChild.style.display = 'block';
    });

    // A top-level item opens its pop-out when collapsed, and otherwise slides
    // its sub-menu (in a .open-current-submenu menu, closing any other first).
    FIRST_SUB_MENUS_BTN.forEach(function (element) {
        element.addEventListener('click', function () {
            if (isCollapsed()) {
                togglePopOut(element.nextElementSibling);
                return;
            }
            var parentMenu = element.closest('.menu.open-current-submenu');
            if (parentMenu) {
                parentMenu.querySelectorAll(':scope > ul > .menu-item.sub-menu > a').forEach(function (el) {
                    if (window.getComputedStyle(el.nextElementSibling).display !== 'none') slideUp(el.nextElementSibling);
                });
            }
            slideToggle(element.nextElementSibling);
        });
    });

    INNER_SUB_MENUS_BTN.forEach(function (element) {
        element.addEventListener('click', function () {
            slideToggle(element.nextElementSibling);
        });
    });
})();
