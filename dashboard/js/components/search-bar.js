/** LogSentry - Search Bar component */
export function renderSearchBar(container, { onSearch, initialQuery = '' } = {}) {
    container.innerHTML = `
    <div class="search-container">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="search-input" class="input" placeholder="Search logs... (e.g., error timeout connection)" value="${initialQuery}" autocomplete="off">
        <span class="search-shortcut">Ctrl+K</span>
    </div>`;

    const input = document.getElementById('search-input');
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => { if (onSearch) onSearch(input.value); }, 300);
    });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(timer); if (onSearch) onSearch(input.value); } });
    document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); input.focus(); input.select(); } });
}
