(function () {
    var initialized = false;

    function init() {
        if (initialized) return;
        if (typeof Chart === 'undefined') return;
        var dataEl = document.getElementById('cards-stats-data');
        var chartsWrap = document.querySelector('.cards-dashboard-charts');
        if (!dataEl || !chartsWrap) return;
        var stats;
        try {
            stats = JSON.parse(dataEl.textContent);
        } catch (e) {
            return;
        }
        if (!stats) return;

        var isClassic = false;
        try { isClassic = localStorage.getItem('theme') === 'classic'; } catch (e) {}

        var palette = isClassic
            ? {
                weak: '#dc2626',
                medium: '#d97706',
                strong: '#16a34a',
                unpracticed: '#94a3b8',
                text: '#1e293b',
                grid: 'rgba(30, 41, 59, 0.12)',
            }
            : {
                weak: '#ff4d6d',
                medium: '#f59e0b',
                strong: '#22c55e',
                unpracticed: '#6b7280',
                text: '#ffffff',
                grid: 'rgba(255, 255, 255, 0.12)',
            };

        Chart.defaults.color = palette.text;
        Chart.defaults.font.family = "'Patrick Hand', system-ui, sans-serif";

        var distEl = document.getElementById('cards-distribution-chart');
        if (distEl && stats.buckets) {
            var b = stats.buckets;
            var labels = [
                chartsWrap.dataset.i18nBucketWeak || 'Weak',
                chartsWrap.dataset.i18nBucketMedium || 'Medium',
                chartsWrap.dataset.i18nBucketStrong || 'Strong',
                chartsWrap.dataset.i18nBucketUnpracticed || 'Unpracticed',
            ];
            new Chart(distEl, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: [b.weak || 0, b.medium || 0, b.strong || 0, b.unpracticed || 0],
                        backgroundColor: [palette.weak, palette.medium, palette.strong, palette.unpracticed],
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: palette.text, padding: 12 } },
                    },
                },
            });
        }

        var weakEl = document.getElementById('cards-weakest-chart');
        if (weakEl && Array.isArray(stats.weakest) && stats.weakest.length) {
            var w = stats.weakest;
            var labels2 = w.map(function (c) {
                var s = (c.front || '') + ' → ' + (c.back || '');
                return s.length > 28 ? s.slice(0, 27) + '…' : s;
            });
            var values = w.map(function (c) {
                return c.score == null ? 0 : Math.round(c.score * 100);
            });
            new Chart(weakEl, {
                type: 'bar',
                data: {
                    labels: labels2,
                    datasets: [{
                        label: '%',
                        data: values,
                        backgroundColor: values.map(function (v) {
                            if (v < 50) return palette.weak;
                            if (v < 80) return palette.medium;
                            return palette.strong;
                        }),
                        borderWidth: 0,
                    }],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            beginAtZero: true, max: 100,
                            ticks: { color: palette.text, callback: function (v) { return v + '%'; } },
                            grid: { color: palette.grid },
                        },
                        y: {
                            ticks: { color: palette.text },
                            grid: { color: palette.grid },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) { return ctx.parsed.x + '%'; },
                            },
                        },
                    },
                },
            });
        }
        initialized = true;
    }

    window.__initCardsDashboardCharts = init;
}());
