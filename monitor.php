<?php
$api_url = "http://127.0.0.1:5001/api/stats";
$ch = curl_init($api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 6);
$json_data = curl_exec($ch);
curl_close($ch);

$stats = json_decode($json_data, true) ?: [];
$period = $_GET['period'] ?? '30d';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa | Analytics Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="25">
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: 'Inter', sans-serif; }
        .card { background: #1e293b; border: none; border-radius: 12px; }
        .nav-pills .nav-link { color: #cbd5e1; }
        .nav-pills .nav-link.active { background: #3b82f6; color: white; }
        .status-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; }
    </style>
</head>
<body class="p-4">
<div class="container">

    <h2 class="mb-4">📊 IndieMa Stream Analytics</h2>

    <!-- Period Filters -->
    <ul class="nav nav-pills mb-4">
        <li class="nav-item"><a class="nav-link <?= $period=='1d'?'active':'' ?>" href="?period=1d">Today</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='7d'?'active':'' ?>" href="?period=7d">7 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='15d'?'active':'' ?>" href="?period=15d">15 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='30d'?'active':'' ?>" href="?period=30d">30 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='90d'?'active':'' ?>" href="?period=90d">3 Months</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='1y'?'active':'' ?>" href="?period=1y">1 Year</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='all'?'active':'' ?>" href="?period=all">All Time</a></li>
    </ul>

    <div class="row">
        <?php foreach ($stats as $s): ?>
        <div class="col-lg-6 mb-4">
            <div class="card p-4 shadow-sm">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h4 class="mb-1"><?= htmlspecialchars($s['name'] ?? 'Unknown') ?></h4>
                        <small class="text-muted">ID: <?= htmlspecialchars($s['id'] ?? '') ?></small>
                    </div>
                    <span class="badge <?= ($s['status'] ?? '') == 'ONLINE' ? 'bg-success' : 'bg-danger' ?>">
                        ● <?= $s['status'] ?? 'OFFLINE' ?>
                    </span>
                </div>
                <hr>
                <div class="row text-center">
                    <div class="col-4">
                        <div class="text-muted small">Clips</div>
                        <h5><?= $s['clip_count'] ?? 0 ?></h5>
                    </div>
                    <div class="col-4 border-start border-end">
                        <div class="text-muted small">Live Viewers</div>
                        <h5 class="text-info"><?= $s['viewers'] ?? 0 ?></h5>
                    </div>
                    <div class="col-4">
                        <div class="text-muted small">Status</div>
                        <h5><?= $s['status'] ?? 'OFFLINE' ?></h5>
                    </div>
                </div>
            </div>
        </div>
        <?php endforeach; ?>
    </div>

    <?php if (empty($stats)): ?>
        <div class="alert alert-warning text-center">No channel data available yet.</div>
    <?php endif; ?>

</div>
</body>
</html>
