// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.


(function() {
    'use strict';

    /**
     * Apply positioning to all elements with data-position attribute
     */
    function applyPositions() {
        // Find all elements with data-position attribute
        const elements = document.querySelectorAll('[data-position]');

        elements.forEach(function(element) {
            const position = element.getAttribute('data-position');

            if (position) {
                // Parse position in format "x,y"
                const coords = position.split(',').map(coord => coord.trim());

                if (coords.length === 2) {
                    const x = coords[0];
                    const y = coords[1];

                    // Apply CSS positioning
                    element.style.left = x + 'px';
                    element.style.top = y + 'px';

                    // Ensure element has position absolute if not already set
                    if (window.getComputedStyle(element).position === 'static') {
                        element.style.position = 'absolute';
                    }
                }
            }
        });

        console.log(`Applied positioning to ${elements.length} elements`);
    }

    /**
     * Initialize positioning when DOM is ready
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', applyPositions);
        } else {
            // DOM already loaded
            applyPositions();
        }
    }

    // Auto-initialize
    init();

    // Expose function globally for manual refresh if needed
    window.applyDataPositions = applyPositions;

})();
