// ============================================================
// Meter Hierarchy - Toggle & Autocomplete Search
// ============================================================

function toggleChildren(element) {
    const li = element.parentElement;
    li.classList.toggle('collapsed');
}

// ── Build a flat list of all meters on page load ──
let meterIndex = [];

function buildMeterIndex() {
    meterIndex = [];
    const allMeters = document.querySelectorAll('.tree .meter');
    allMeters.forEach(function (meterEl) {
        const idSpan = meterEl.querySelector('.meter-id');
        const typeSpan = meterEl.querySelector('.meter-type');
        if (!idSpan) return;
        meterIndex.push({
            name: idSpan.textContent.trim(),
            type: typeSpan ? typeSpan.textContent.trim() : '',
            element: meterEl,
            li: meterEl.closest('li')
        });
    });
}

// ── Autocomplete dropdown logic ──

function showDropdown(dropdown, searchBox) {
    dropdown.classList.add('active');
    searchBox.classList.add('dropdown-open');
}

function hideDropdown(dropdown, searchBox) {
    dropdown.classList.remove('active');
    searchBox.classList.remove('dropdown-open');
}

/**
 * Highlight the matched portion of text with <mark> tags.
 */
function highlightMatch(text, term) {
    if (!term) return escapeHtml(text);
    var lower = text.toLowerCase();
    var idx = lower.indexOf(term.toLowerCase());
    if (idx === -1) return escapeHtml(text);
    var before = text.substring(0, idx);
    var match = text.substring(idx, idx + term.length);
    var after = text.substring(idx + term.length);
    return escapeHtml(before) + '<mark>' + escapeHtml(match) + '</mark>' + escapeHtml(after);
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * Populate the dropdown with matching meters.
 */
function populateDropdown(dropdown, searchBox, term) {
    dropdown.innerHTML = '';

    if (!term) {
        hideDropdown(dropdown, searchBox);
        return;
    }

    var lowerTerm = term.toLowerCase();
    var matches = [];
    for (var i = 0; i < meterIndex.length; i++) {
        if (meterIndex[i].name.toLowerCase().indexOf(lowerTerm) !== -1) {
            matches.push(meterIndex[i]);
        }
    }

    if (matches.length === 0) {
        dropdown.innerHTML = '<div class="search-dropdown-empty">No meters found</div>';
        showDropdown(dropdown, searchBox);
        return;
    }

    // Limit to 20 results for performance
    var limit = Math.min(matches.length, 20);
    for (var j = 0; j < limit; j++) {
        var m = matches[j];
        var item = document.createElement('div');
        item.className = 'search-dropdown-item';
        item.setAttribute('data-index', meterIndex.indexOf(m));
        item.innerHTML =
            '<span class="dropdown-meter-icon">⚡</span>' +
            '<span class="dropdown-meter-name">' + highlightMatch(m.name, term) + '</span>' +
            '<span class="dropdown-meter-type">' + escapeHtml(m.type) + '</span>';
        dropdown.appendChild(item);
    }

    if (matches.length > limit) {
        var more = document.createElement('div');
        more.className = 'search-dropdown-empty';
        more.style.color = 'var(--bs-secondary-color, #7d84ab)';
        more.textContent = '… and ' + (matches.length - limit) + ' more results';
        dropdown.appendChild(more);
    }

    showDropdown(dropdown, searchBox);
}

/**
 * Navigate to a meter in the hierarchy tree:
 *  1. Collapse everything
 *  2. Expand all ancestor <li> nodes
 *  3. Highlight and scroll to the meter
 */
function navigateToMeter(meterData) {
    // Clear previous highlights
    document.querySelectorAll('.tree .highlight').forEach(function (el) {
        el.classList.remove('highlight');
    });

    // Collapse all tree items that have children
    document.querySelectorAll('.tree li').forEach(function (li) {
        if (li.querySelector('ul')) {
            li.classList.add('collapsed');
        }
    });

    var targetLi = meterData.li;
    var targetMeter = meterData.element;

    // Expand the target itself (if it has children)
    targetLi.classList.remove('collapsed');

    // Walk up the DOM tree and expand all ancestor <li> elements
    var parent = targetLi.parentElement;
    while (parent) {
        var parentLi = parent.closest('li');
        if (parentLi) {
            parentLi.classList.remove('collapsed');
            parent = parentLi.parentElement;
        } else {
            break;
        }
    }

    // Highlight the target meter and all its parent meters
    targetMeter.classList.add('highlight');

    // Walk up the tree and highlight all ancestor meters
    var currentLi = targetLi;
    while (currentLi) {
        var parentUl = currentLi.parentElement;
        if (!parentUl || parentUl.tagName !== 'UL') break;
        var grandparentLi = parentUl.parentElement;
        if (!grandparentLi || grandparentLi.tagName !== 'LI') break;
        // Find the direct child <a> with class 'meter' in this ancestor <li>
        var kids = grandparentLi.children;
        for (var k = 0; k < kids.length; k++) {
            if (kids[k].tagName === 'A' && kids[k].classList.contains('meter')) {
                kids[k].classList.add('highlight');
                break;
            }
        }
        currentLi = grandparentLi;
    }

    // Scroll into view after a short delay for the tree to expand
    setTimeout(function () {
        targetMeter.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }, 350);
}

// ── Keyboard navigation state ──
var activeDropdownIndex = -1;

function setActiveItem(dropdown, index) {
    var items = dropdown.querySelectorAll('.search-dropdown-item');
    // Clear previous active
    items.forEach(function (el) { el.classList.remove('active'); });
    activeDropdownIndex = index;
    if (index >= 0 && index < items.length) {
        items[index].classList.add('active');
        // Scroll into view within dropdown
        items[index].scrollIntoView({ block: 'nearest' });
    }
}

// ── Init on DOM ready ──
document.addEventListener('DOMContentLoaded', function () {
    // Collapse all meters initially
    document.querySelectorAll('.tree li').forEach(function (li) {
        if (li.querySelector('ul')) {
            li.classList.add('collapsed');
        }
    });

    // Build the meter index
    buildMeterIndex();

    var searchBox = document.getElementById('searchBox');
    var dropdown = document.getElementById('searchDropdown');
    if (!searchBox || !dropdown) return;

    // ── Input event: live filter on each keystroke ──
    searchBox.addEventListener('input', function () {
        activeDropdownIndex = -1;
        populateDropdown(dropdown, searchBox, searchBox.value.trim());
    });

    // ── Keyboard navigation: ArrowDown, ArrowUp, Enter, Escape ──
    searchBox.addEventListener('keydown', function (e) {
        var items = dropdown.querySelectorAll('.search-dropdown-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            var next = activeDropdownIndex + 1;
            if (next >= items.length) next = 0;
            setActiveItem(dropdown, next);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            var prev = activeDropdownIndex - 1;
            if (prev < 0) prev = items.length - 1;
            setActiveItem(dropdown, prev);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeDropdownIndex >= 0 && activeDropdownIndex < items.length) {
                items[activeDropdownIndex].click();
            }
        } else if (e.key === 'Escape') {
            hideDropdown(dropdown, searchBox);
            searchBox.blur();
        }
    });

    // ── Click on a dropdown item: navigate in tree ──
    dropdown.addEventListener('click', function (e) {
        var item = e.target.closest('.search-dropdown-item');
        if (!item) return;

        var idx = parseInt(item.getAttribute('data-index'), 10);
        if (isNaN(idx) || !meterIndex[idx]) return;

        // Navigate to that meter in the tree
        navigateToMeter(meterIndex[idx]);

        // Put the meter name in the search box and close dropdown
        searchBox.value = meterIndex[idx].name;
        hideDropdown(dropdown, searchBox);
    });

    // ── Close dropdown when clicking outside ──
    document.addEventListener('click', function (e) {
        if (!searchBox.contains(e.target) && !dropdown.contains(e.target)) {
            hideDropdown(dropdown, searchBox);
        }
    });

    // ── Re-show dropdown when focusing back into search box (if there's text) ──
    searchBox.addEventListener('focus', function () {
        if (searchBox.value.trim()) {
            populateDropdown(dropdown, searchBox, searchBox.value.trim());
        }
    });
});
