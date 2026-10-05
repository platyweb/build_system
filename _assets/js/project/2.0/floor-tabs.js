// Tab switching for floor and tenant floor pages. Zone header colours come
// from meter-templates.js, which gives each meter row it generates a
// meter-<utility> class from the meter's meters.csv utility code.
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
