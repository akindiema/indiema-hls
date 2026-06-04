<?php
$api_url = "http://127.0.0.1:5001/api/stats";
$ch = curl_init($api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 6);
$json = curl_exec($ch);
curl_close($ch);
$stats = json_decode($json, true) ?: [];

$period = $_GET['period'] ?? '30d';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="25">
    <style>
        body { background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; border: none; }
        .nav-pills .nav-link.active { background: #3b82f6; }
    </style>
</head>
<body class="p-4">
<div class="container">
    <h2 class="mb-4">📊 IndieMa Stream Analytics</h2>

    <ul class="nav nav-pills mb-4">
        <li class="nav-item"><a class="nav-link <?= $period=='1d'?'active':'' ?>" href="?period=1d">Today</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='7d'?'active':'' ?>" href="?period=7d">7 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='15d'?'active':'' ?>" href="?period=15d">15 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='30d'?'active':'' ?>" href="?period=30d">30 Days</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='90d'?'active':'' ?>" href="?period=90d">3 Months</a></li>
        <li class="nav-item"><a class="nav-link <?= $period=='1y'?'active':'' ?>" href="?period=1y">1 Year</a></li>
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
                <div class="row text-center">
                    <div class="col-4">
                        <small>Clips</small><br>
                        <strong><?= $s['clip_count'] ?? 0 ?></strong>
                    </div>
                    <div class="col-4">
                        <small>Live Viewers</small><br>
                        <strong class="text-info"><?= $s['viewers'] ?? 0 ?></strong>
                    </div>
                    <div class="col-4">
                        <small>Status</small><br>
                        <strong><?= $s['status'] ?? 'OFFLINE' ?></strong>
                    </div>
                </div>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
</div>
</body>
</html>
