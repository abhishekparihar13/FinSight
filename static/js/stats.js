// Dark Finance Pro - Chart Configurations
const bgColors = [
    '#7C3AED', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', 
    '#EC4899', '#8B5CF6', '#14B8A6', '#F97316', '#6366F1',
    '#3B82F6', '#84CC16', '#F43F5E', '#D946EF', '#0EA5E9'
];

let doughnutChartInstance = null;
let barChartInstance = null;
let allExpenses = [];

// Helper to get CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const fetchAllExpenses = () => {
    const spinner = document.getElementById('loadingSpinner');
    const container = document.getElementById('chartsContainer');

    // We use search-expenses with "" to match all dates and expenses accurately
    fetch("/search-expenses", {
        method: "POST",
        body: JSON.stringify({ searchText: "" }),
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(res => res.json())
    .then(data => {
        allExpenses = data;
        
        // Hide loading spinner, show charts
        if (spinner) spinner.classList.add('hidden');
        if (container) container.classList.remove('hidden');
        if (window.lucide) window.lucide.createIcons();
        
        updateCharts(30); // Default 30 days
        setupFilters();
    })
    .catch(e => {
        console.error("Failed to fetch expenses for charts", e);
        fetchCategorySummaryFallback();
    });
};

const fetchCategorySummaryFallback = () => {
    fetch("/expense_category_summary")
    .then(res => res.json())
    .then(results => {
        const catData = results.expense_category_data;
        const labels = Object.keys(catData);
        const data = Object.values(catData);
        const total = data.reduce((a, b) => a + b, 0);
        renderDoughnut(labels, data, total);
        renderBar([], []); // Empty bar chart
    });
}

const updateCharts = (days) => {
    const now = new Date();
    // Reset time to start of day for accurate day differences
    now.setHours(23, 59, 59, 999);
    const cutoff = new Date(now.getTime() - (days * 24 * 60 * 60 * 1000));
    cutoff.setHours(0,0,0,0);
    
    // Filter data
    const filtered = allExpenses.filter(e => {
        const isAfterCutoff = new Date(e.date) >= cutoff;
        const isNotInvestment = !e.category.toLowerCase().includes('investment');
        return isAfterCutoff && isNotInvestment;
    });
    
    // Process Category Data for Doughnut
    const catData = {};
    let total = 0;
    filtered.forEach(e => {
        catData[e.category] = (catData[e.category] || 0) + parseFloat(e.amount);
        total += parseFloat(e.amount);
    });
    
    // Process Daily Data for Bar Chart
    const dailyData = {};
    // Pre-fill days to show zero
    for(let i = days - 1; i >= 0; i--) {
        const d = new Date(now.getTime() - (i * 24 * 60 * 60 * 1000));
        const dateStr = d.toISOString().split('T')[0];
        dailyData[dateStr] = 0;
    }
    filtered.forEach(e => {
        const dateStr = new Date(e.date).toISOString().split('T')[0];
        if(dailyData[dateStr] !== undefined) {
            dailyData[dateStr] += parseFloat(e.amount);
        }
    });

    renderDoughnut(Object.keys(catData), Object.values(catData), total);
    renderBar(Object.keys(dailyData), Object.values(dailyData));
};

// Format date for bar chart labels (e.g. "Apr 15")
const formatDate = (dateString) => {
    const d = new Date(dateString + 'T12:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const renderDoughnut = (labels, data, total) => {
    const ctx = document.getElementById("myChart");
    if(doughnutChartInstance) doughnutChartInstance.destroy();

    doughnutChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: bgColors.slice(0, labels.length),
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            cutout: '75%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 24, 0.9)',
                    titleColor: '#F8FAFC',
                    bodyColor: '#F8FAFC',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true
                }
            }
        }
    });

    // Custom Legend Render
    const legendContainer = document.getElementById('chart-legend');
    legendContainer.innerHTML = '';
    labels.forEach((label, i) => {
        const amount = data[i];
        const color = bgColors[i % bgColors.length];
        
        legendContainer.innerHTML += `
            <div class="flex items-center text-sm py-1.5">
                <div class="w-3 h-3 rounded-full shrink-0 mr-3" style="background-color: ${color}"></div>
                <span class="text-muted text-sm capitalize truncate" title="${label}">${label}</span>
            </div>
        `;
    });
};

const renderBar = (labels, data) => {
    const ctx = document.getElementById("trendChart");
    if(barChartInstance) barChartInstance.destroy();

    const formattedLabels = labels.map(l => formatDate(l));

    barChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: formattedLabels,
            datasets: [{
                label: "Daily Spend",
                data: data,
                backgroundColor: '#9d4edd', // Neon Purple
                borderRadius: 4,
                borderWidth: 0,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 17, 24, 0.9)',
                    titleColor: '#F8FAFC',
                    bodyColor: '#F8FAFC',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94A3B8', padding: 10 },
                    beginAtZero: true
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94A3B8', maxRotation: 45, minRotation: 45 }
                }
            }
        }
    });
};

const setupFilters = () => {
    const btns = document.querySelectorAll('.filter-btn');

    btns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            btns.forEach(b => {
                b.classList.remove('text-light', 'active');
                b.classList.add('text-muted');
            });
            e.target.classList.remove('text-muted');
            e.target.classList.add('text-light', 'active');
            
            const days = parseInt(e.target.getAttribute('data-days'));
            updateCharts(days);
        });
    });
};

window.onload = fetchAllExpenses;
