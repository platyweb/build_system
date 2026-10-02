/**
 * Report Template System
 * Creates reusable report pages with parameterized title, link, and image
 * Supports single or multiple reports on one page.
 *
 * Single report usage (backward compatible):
 *   report_template.htm?title=Baseline Report&href=/path&imageSrc=baseline
 *
 * Multiple reports usage (indexed parameters):
 *   report_template.htm?title=Reports&href0=/path1&imageSrc0=baseline&label0=Daily Baseline&href1=/path2&imageSrc1=occupancyAnalysis&label1=Occupancy
 */

/**
 * Creates a complete report page structure (single report - backward compatible)
 * @param {Object} options - Report configuration options
 * @param {string} options.title - Page title text
 * @param {string} options.href - Link URL for the report card
 * @param {string} options.imageSrc - Image source URL
 * @param {string} [options.imageAlt='Report Image'] - Alt text for image
 * @param {string} [options.imageWidth='100%'] - Image max-width (default: 100%)
 * @returns {void} Updates the DOM directly
 */
function createReportPage(options) {
    const {
        title,
        href,
        imageSrc,
        imageAlt = 'Report Image',
        imageWidth = '100%'
    } = options;

    // Update the title
    const titleElement = document.querySelector('.title-bar h1');
    if (titleElement) {
        titleElement.textContent = title;
    }

    // Update the link href
    const linkElement = document.querySelector('a.switchboard-card');
    if (linkElement) {
        linkElement.href = href;
    }

    // Update the image
    const imageElement = document.querySelector('.floorplan-placeholder img');
    if (imageElement) {
        imageElement.src = imageSrc;
        imageElement.alt = imageAlt;
        imageElement.style.maxWidth = imageWidth;
    }
}

/**
 * Creates a multi-report page with multiple report cards stacked vertically
 * @param {string} title - Page title text
 * @param {Array<Object>} reports - Array of report configurations
 * @param {string} reports[].href - Link URL for the report card
 * @param {string} reports[].imageSrc - Image source URL (key name or direct URL)
 * @param {string} [reports[].label] - Optional sub-heading label for this report
 * @param {string} [reports[].imageAlt='Report Image'] - Alt text for image
 * @param {string} [reports[].imageWidth='100%'] - Image max-width
 * @returns {void} Updates the DOM directly
 */
function createMultiReportPage(title, reports) {
    // Update the page title
    const titleElement = document.querySelector('.title-bar h1');
    if (titleElement) {
        titleElement.textContent = title;
    }

    // Get the container where report cards go
    const container = document.querySelector('.container');
    if (!container) return;

    // Remove the existing single report card placeholder (the <a> element)
    const existingCard = container.querySelector('a.switchboard-card');
    if (existingCard) {
        existingCard.remove();
    }

    // Create and append each report card
    reports.forEach(function(report) {
        // If there's a label, add a sub-heading
        if (report.label) {
            const subHeading = document.createElement('div');
            subHeading.className = 'report-sub-heading';
            subHeading.innerHTML = '<h2>' + report.label + '</h2>';
            container.appendChild(subHeading);
        }

        // Create the report card using the existing helper
        const card = createReportCard({
            href: report.href,
            imageSrc: report.imageSrc,
            imageAlt: report.imageAlt || 'Report Image',
            imageWidth: report.imageWidth || '100%'
        });
        card.setAttribute('target', '_blank');
        // Ensure the card can grow to fit its content (override overflow:hidden)
        card.style.overflow = 'visible';
        card.style.height = 'auto';

        // Also ensure the inner viewer and placeholder can expand fully
        var viewer = card.querySelector('.floorplan-viewer');
        if (viewer) {
            viewer.style.minHeight = 'auto';
            viewer.style.height = 'auto';
        }
        var placeholder = card.querySelector('.floorplan-placeholder');
        if (placeholder) {
            placeholder.style.display = 'block';
            placeholder.style.width = '100%';
        }
        var img = card.querySelector('img');
        if (img) {
            img.style.width = '100%';
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
        }

        container.appendChild(card);
    });
}

/**
 * Creates a report card element (for use in other contexts)
 * @param {Object} options - Report card configuration
 * @param {string} options.href - Link URL
 * @param {string} options.imageSrc - Image source URL
 * @param {string} [options.imageAlt='Report Image'] - Alt text for image
 * @param {string} [options.imageWidth='100%'] - Image max-width
 * @param {string} [options.customClass=''] - Additional CSS classes
 * @returns {HTMLElement} The created report card element
 */
function createReportCard(options) {
    const {
        href,
        imageSrc,
        imageAlt = 'Report Image',
        imageWidth = '100%',
        customClass = ''
    } = options;

    // Create the link wrapper
    const link = document.createElement('a');
    link.href = href;
    link.className = `switchboard-card primary ${customClass}`.trim();

    // Create the floorplan viewer
    const viewer = document.createElement('div');
    viewer.className = 'floorplan-viewer';

    // Create the placeholder
    const placeholder = document.createElement('div');
    placeholder.className = 'floorplan-placeholder';

    // Create the image
    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = imageAlt;
    img.style.maxWidth = imageWidth;
    img.style.height = 'auto';
    img.style.display = 'block';

    // Assemble the structure
    placeholder.appendChild(img);
    viewer.appendChild(placeholder);
    link.appendChild(viewer);

    return link;
}

/**
 * Updates an existing report page with new values
 * @param {Object} options - Update configuration
 * @param {string} [options.title] - New title text
 * @param {string} [options.href] - New link URL
 * @param {string} [options.imageSrc] - New image source
 * @param {string} [options.imageAlt] - New image alt text
 * @param {string} [options.imageWidth] - New image width
 */
function updateReportPage(options) {
    if (options.title) {
        const titleElement = document.querySelector('.title-bar h1');
        if (titleElement) {
            titleElement.textContent = options.title;
        }
    }

    if (options.href) {
        const linkElement = document.querySelector('a.switchboard-card');
        if (linkElement) {
            linkElement.href = options.href;
        }
    }

    if (options.imageSrc || options.imageAlt || options.imageWidth) {
        const imageElement = document.querySelector('.floorplan-placeholder img');
        if (imageElement) {
            if (options.imageSrc) imageElement.src = options.imageSrc;
            if (options.imageAlt) imageElement.alt = options.imageAlt;
            if (options.imageWidth) imageElement.style.maxWidth = options.imageWidth;
        }
    }
}

/**
 * Predefined report templates
 */
const REPORT_TEMPLATES = {
    baseline: {
        title: 'Baseline Consumption Report',
        imageAlt: 'Baseline Report Chart',
        imageWidth: '100%'
    },
    performance: {
        title: 'Performance Analysis Report',
        imageAlt: 'Performance Chart',
        imageWidth: '100%'
    },
    energy: {
        title: 'Energy Consumption Report',
        imageAlt: 'Energy Chart',
        imageWidth: '100%'
    },
    comparison: {
        title: 'Comparative Analysis Report',
        imageAlt: 'Comparison Chart',
        imageWidth: '100%'
    }
};

/**
 * Helper function to use a predefined template with custom options
 * @param {string} templateName - Name of template from REPORT_TEMPLATES
 * @param {Object} customOptions - Custom options to override template
 * @returns {Object} Merged configuration
 */
function useReportTemplate(templateName, customOptions) {
    const template = REPORT_TEMPLATES[templateName] || {};
    return { ...template, ...customOptions };
}

// Export functions for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createReportPage,
        createReportCard,
        updateReportPage,
        useReportTemplate,
        REPORT_TEMPLATES
    };
}
