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
    run: (cat, func) => `/api/run/${cat}/${func}`,
};

// Функции, разрешённые для запуска из веба
const ALLOWED_TO_RUN = {
    system: ['health_check', 'info'],
    network: ['scan'],
    backup: ['list'],
    ad: ['users', 'audit', 'passwords'],
    reports: ['generate', 'history'],
    printers: ['monitor', 'local_scanner', 'reports'],
};

// =====================================================================
// Утилиты
// =====================================================================

async function fetchJSON(url, options = {}) {
    try {
        const res = await fetch(url, options);
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
                <div class="value">${escapeHtml(data.hostname)}</div>
            </div>
            <div class="info-item">
                <div class="label">ОС</div>
                <div class="value">${escapeHtml(data.os)}</div>
            </div>
            <div class="info-item">
                <div class="label">Версия</div>
                <div class="value">${escapeHtml(data.release)}</div>
            </div>
            <div class="info-item">
                <div class="label">Время</div>
                <div class="value">${new Date(data.time).toLocaleString('ru-RU')}</div>
            </div>
        </div>
    `;
}

// =====================================================================
// Категории с кнопками
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
        const allowed = ALLOWED_TO_RUN[key] || [];

        const functionsHtml = cat.functions
            .filter(f => f.enabled !== false)
            .map(f => {
                const canRun = allowed.includes(f.id);
                const runBtn = canRun
                    ? `<button class="run-btn" onclick="runFunction('${key}', '${f.id}', this)" title="Запустить">▶</button>`
                    : '<span class="no-run" title="Только в консоли">—</span>';
                return `<li>${runBtn} ${escapeHtml(f.name)}</li>`;
            })
            .join('');

        card.innerHTML = `
            <div class="title">${escapeHtml(cat.name)}</div>
            <ul class="functions">${functionsHtml}</ul>
        `;
        grid.appendChild(card);
    }
}

// =====================================================================
// Запуск функции
// =====================================================================

async function runFunction(category, funcId, btn) {
    // Блокируем кнопку
    const originalText = btn.textContent;
    btn.textContent = '⏳';
    btn.disabled = true;

    // Показываем модальное окно с результатом
    openResultModal(category, funcId);

    try {
        const res = await fetch(API.run(category, funcId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();

        // Показываем результат
        const output = document.getElementById('result-output');
        if (data.ok) {
            output.textContent = data.output || '(нет вывода)';
        } else {
            output.textContent = `Ошибка: ${data.error}\n\n${data.output || ''}`;
            output.style.color = '#f85149';
        }

        // Обновляем виджеты
        setTimeout(() => {
            loadHealth();
            loadPrinters();
            loadBackups();
            loadNetwork();
            loadReports();
        }, 500);

    } catch (e) {
        const output = document.getElementById('result-output');
        output.textContent = `Ошибка: ${e.message}`;
        output.style.color = '#f85149';
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// =====================================================================
// Модальное окно результата
// =====================================================================

function openResultModal(category, funcId) {
    const modal = document.getElementById('result-modal');
    const title = document.getElementById('result-title');
    const output = document.getElementById('result-output');

    title.textContent = `Запуск: ${category}.${funcId}`;
    output.textContent = '⏳ Выполняется...';
    output.style.color = '#c9d1d9';

    modal.classList.add('active');
}

function closeResultModal() {
    document.getElementById('result-modal').classList.remove('active');
}

// =====================================================================
// Health Check
// =====================================================================

async function loadHealth() {
    const widget = document.getElementById('widget-health');
    const content = widget.querySelector('.widget-content');

    const data = await fetchJSON(API.health);
    if (!data.ok) {
        content.innerHTML = '<span class="critical">Ошибка</span>';
        return;
    }

    const s = data.summary;
    content.innerHTML = `
        <div class="big-number">${s.ok}/${s.total}</div>
        <div class="sub">
            <span class="ok">🟢 ${s.ok}</span> |
            <span class="warning">🟡 ${s.warning}</span> |
            <span class="critical">🔴 ${s.critical}</span>
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
        <div class="sub">принтеров</div>
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
        <div class="sub">бэкапов</div>
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
        <div class="sub">устройств</div>
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
            <span class="name">${escapeHtml(r.name)}</span>
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
