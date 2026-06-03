/**
 * LogSentry - Chart.js wrapper with dark theme defaults
 */
const chartInstances = {};

const darkTheme = {
    color: '#94a3b8',
    borderColor: 'rgba(59, 130, 246, 0.1)',
    font: { family: "'Inter', sans-serif" },
};

export function createAreaChart(canvasId, labels, datasets, title = '') {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: datasets.map((ds, i) => ({
                label: ds.label || 'Value',
                data: ds.data,
                borderColor: ds.color || '#3b82f6',
                backgroundColor: i === 0 ? gradient : 'transparent',
                fill: i === 0,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: ds.color || '#3b82f6',
            })),
        },
        options: getOptions(title),
    });
    return chartInstances[canvasId];
}

export function createBarChart(canvasId, labels, data, title = '') {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    chartInstances[canvasId] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: labels.map((_, i) => `hsla(${210 + i * 30}, 70%, 55%, 0.7)`),
                borderRadius: 4,
                borderSkipped: false,
            }],
        },
        options: { ...getOptions(title), plugins: { ...getOptions(title).plugins, legend: { display: false } } },
    });
    return chartInstances[canvasId];
}

export function createDoughnutChart(canvasId, labels, data, colors, title = '') {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    chartInstances[canvasId] = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data, backgroundColor: colors, borderWidth: 0, spacing: 2 }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11, family: "'Inter'" }, padding: 12, usePointStyle: true, pointStyleWidth: 10 } },
                title: { display: !!title, text: title, color: '#f1f5f9', font: { size: 13, weight: '600' }, padding: { bottom: 12 } },
            },
        },
    });
    return chartInstances[canvasId];
}

export function updateChart(canvasId, labels, data) {
    const chart = chartInstances[canvasId];
    if (!chart) return;
    chart.data.labels = labels;
    if (Array.isArray(data[0])) {
        data.forEach((d, i) => { if (chart.data.datasets[i]) chart.data.datasets[i].data = d; });
    } else {
        chart.data.datasets[0].data = data;
    }
    chart.update('none');
}

function destroyChart(id) { if (chartInstances[id]) { chartInstances[id].destroy(); delete chartInstances[id]; } }

function getOptions(title) {
    return {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        scales: {
            x: { grid: { color: 'rgba(59,130,246,0.06)' }, ticks: { color: '#64748b', font: { size: 10 } } },
            y: { grid: { color: 'rgba(59,130,246,0.06)' }, ticks: { color: '#64748b', font: { size: 10 } }, beginAtZero: true },
        },
        plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 11, family: "'Inter'" }, usePointStyle: true } },
            title: { display: !!title, text: title, color: '#f1f5f9', font: { size: 13, weight: '600' }, padding: { bottom: 12 } },
            tooltip: {
                backgroundColor: 'rgba(15,22,41,0.95)', titleColor: '#f1f5f9', bodyColor: '#94a3b8',
                borderColor: 'rgba(59,130,246,0.2)', borderWidth: 1, cornerRadius: 8, padding: 10,
                titleFont: { family: "'Inter'", weight: '600' }, bodyFont: { family: "'Inter'" },
            },
        },
        animation: { duration: 700, easing: 'easeOutQuart' },
    };
}
