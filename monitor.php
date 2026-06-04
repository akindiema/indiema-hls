<?php
$api_url = "http://127.0.0.1:5001/api/stats";
$ch = curl_init($api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$json = curl_exec($ch);
curl_close($ch);
$stats = json_decode($json, true) ?: [];

$period = $_GET['period'] ?? '30d';
$selected_channel = $_GET['channel'] ?? '';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <meta http-equiv="refresh" content="30">
    <style>
        body { background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; border: none; }
        canvas { max-height: 320px; }
    </style>
</head>
<body class="p-4">
<div class="container">
    <h2 class="mb-4">📊 IndieMa Analytics Dashboard</h2>

    <div class="mb-4">
        <a href="/api/export" class="btn btn-success btn-sm">📥 Export All to CSV</a>
    </div>

    <ul class="nav nav-pills mb-4">
        <li class="nav-item"><a class="nav-link <?= $period=='1d'?'active':'' ?>" href="?period=1d">Today</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='7d'?'active':'' ?>" href="?period=7d">7 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='15d'?'active':'' ?>" href="?period=15d">15 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='30d'?'active':'' ?>" href="?period=30d">30 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='90d'?'active':'' ?>" href="?period=90d">3 Months</a></li>
    </ul>

    <div class="row">
        <?php foreach ($stats as $s): ?>
        <div class="col-lg-6 mb-4">
            <div class="card p-4">
                <div class="d-flex justify-content-between">
                    <h4><?=htmlspecialchars($s['name'])?></h4>
                    <span class="badge <?= ($s['status']??'')=='ONLINE' ? 'bg-success' : 'bg-danger' ?>">
                        ● <?= $s['status'] ?? 'OFFLINE' ?>
                    </span>
                </div>
                <hr>
                <div class="row text-center mb-3">
                    <div class="col-6">
                        <small>Live Viewers</small><br>
                        <h3 class="text-info"><?= $s['viewers'] ?? 0 ?></h3>
                    </div>
                    <div class="col-6">
                        <small>Clips</small><br>
                        <h3><?= $s['clip_count'] ?? 0 ?></h3>
                    </div>
                </div>
                <canvas id="chart-<?= $s['id'] ?>"></canvas>
                <a href="/api/export?channel=<?= $s['id'] ?>" class="btn btn-outline-light btn-sm mt-2">Export CSV</a>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
</div>

<script>
document.querySelectorAll('canvas').forEach(canvas => {
    const channelId = canvas.id.replace('chart-', '');
    fetch(`/api/analytics?channel=${channelId}&days=<?= $period ?>`)
        .then(r => r.json())
        .then(data => {
            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: data.map(item => item.time.substring(11,16)),
                    datasets: [{
                        label: 'Viewers',
                        data: data.map(item => item.viewers),
                        borderColor: '#60a5fa',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } }
                }
            });
        });
});
</script>
</body>
</html>
