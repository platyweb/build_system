function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
    });

    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) selectedTab.classList.add('active');

    const clickedButton = document.querySelector(`.tab-button[onclick*="'${tabName}'"]`);
    if (clickedButton) {
        clickedButton.classList.add('active');
        clickedButton.setAttribute('aria-selected', 'true');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const subheaders = document.querySelectorAll('.floor-stats-subheader');
    subheaders.forEach(header => {
        const text = header.textContent.trim();
        if (text.includes('lphw')) {
            header.classList.add('meter-lphw');
        } else if (text.includes('CHW')) {
            header.classList.add('meter-chw');
        } else if (text.includes('Electricity')) {
            header.classList.add('meter-electricity');
        }
    });
});
