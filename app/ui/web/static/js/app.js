/* =====================================================================
   SYSADMIN-USB — JavaScript веб-интерфейса
   ===================================================================== */

const API = {
    status: '/api/status',
    categories: '/api/categories',
    health: '/api/health',
    printers: '/api/printers',
    backups: '/api/backups',
    network: '/api/network/last',
    reports: '/api/reports',
};

// =====================================================================
// Утилиты
// =====================================================================

async function fetchJSON(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error(`Ошибка ${url}:`, e);
        return { ok: false, error: e.message };
    }
}

function el(tag, className = '', text = '') {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text) e.textContent = text;
    return e;
}

// =====================================================================
// Системная информация
// =====================================================================

async function loadSystemInfo() {
    const data = await fetchJSON(API.status);
    const container = document.getElementById('system-info');

    if (!data.ok) {
        container.innerHTML = '<div class="loading">Не удалось загрузить информацию</div>';
        return;
    }

    container.innerHTML = `
        <div class="info-grid">
            <div class="info-item">
                <div class="label">Hostname</div>
                <div class="value">${data.hostname}</div>
            </div>
            <div class="info-item">
                <div class="label">ОС</div>
                <div class="value">${data.os}</div>
            </div>
            <div class="info-item">
                <div class="label">Версия</div>
                <div class="value">${data.release}</div>
            </div>
            <div class="info-item">
                <div class="label">Время</div>
                <div class="value">${new Date(data.time).toLocaleString('ru-RU')}</div>
            </div>
        </div>
    `;
}

// =====================================================================
// Категории
// =====================================================================

async function loadCategories() {
    const data = await fetchJSON(API.categories);
    const grid = document.getElementById('categories-grid');

    if (!data || Object.keys(data).length === 0) {
        grid.innerHTML = '<div class="loading">Нет категорий</div>';
        return;
    }

    grid.innerHTML = '';
    for (const [key, cat] of Object.entries(data)) {
        const card = el('div', 'category-card');
        card.innerHTML = `
            <div class="title">${cat.name}</div>
            <ul class="functions">
                ${cat.functions.filter(f => f.enabled !== false).map(f => `<li>${f.name}</li>`).join('')}
            </ul>
        `;
        grid.appendChild(card);
    }
}

// =====================================================================
// Health Check
// =====================================================================

async function loadHealth() {
    const widget = document.getElementById('widget-health');
    const content = widget.querySelector('.widget-content');

    const data = await fetchJSON(API.health);
    if (!data.ok) {
        content.innerHTML = '<span class="critical">Ошибка: ' + data.error + '</span>';
        return;
    }

    const s = data.summary;
    content.innerHTML = `
        <div class="big-number">${s.ok}/${s.total}</div>
        <div class="sub">
            <span class="ok">🟢 OK: ${s.ok}</span> |
            <span class="warning">🟡 Warn: ${s.warning}</span> |
            <span class="critical">🔴 Crit: ${s.critical}</span>
        </div>
    `;
}

// =====================================================================
// Принтеры
// =====================================================================

async function loadPrinters() {
    const widget = document.getElementById('widget-printers');
    const content = widget.querySelector('.widget-content');

    const data = await fetchJSON(API.printers);
    if (!data.ok) {
        content.innerHTML = '<span class="critical">Ошибка</span>';
        return;
    }

    content.innerHTML = `
        <div class="big-number">${data.count}</div>
        <div class="sub">принтеров настроено</div>
    `;
}

// =====================================================================
// Бэкапы
// =====================================================================

async function loadBackups() {
    const widget = document.getElementById('widget-backups');
    const content = widget.querySelector('.widget-content');

    const data = await fetchJSON(API.backups);
    if (!data.ok) {
        content.innerHTML = '<span class="critical">Ошибка</span>';
        return;
    }

    content.innerHTML = `
        <div class="big-number">${data.count}</div>
        <div class="sub">бэкапов создано</div>
    `;
}

// =====================================================================
// Сеть
// =====================================================================

async function loadNetwork() {
    const widget = document.getElementById('widget-network');
    const content = widget.querySelector('.widget-content');

    const data = await fetchJSON(API.network);
    if (!data.ok) {
        content.innerHTML = '<span class="critical">Ошибка</span>';
        return;
    }

    content.innerHTML = `
        <div class="big-number">${data.count}</div>
        <div class="sub">устройств в сети</div>
    `;
}

// =====================================================================
// Отчёты
// =====================================================================

async function loadReports() {
    const container = document.getElementById('reports-list');
    const data = await fetchJSON(API.reports);

    if (!data.ok || data.reports.length === 0) {
        container.innerHTML = '<div class="loading">Отчётов пока нет</div>';
        return;
    }

    container.innerHTML = data.reports.map(r => `
        <div class="report-item">
            <span class="name">${r.name}</span>
            <span class="meta">${r.date} — ${(r.size / 1024).toFixed(1)} КБ</span>
        </div>
    `).join('');
}

// =====================================================================
// Инициализация
// =====================================================================

async function init() {
    await loadSystemInfo();
    await loadCategories();
    await Promise.all([
        loadHealth(),
        loadPrinters(),
        loadBackups(),
        loadNetwork(),
    ]);
    await loadReports();

    // Обновление каждые 30 секунд
    setInterval(() => {
        loadHealth();
        loadPrinters();
        loadBackups();
        loadNetwork();
    }, 30000);
}

document.addEventListener('DOMContentLoaded', init);
