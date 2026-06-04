<?php
$api_url = "http://127.0.0.1:5001/api/stats";
$ch = curl_init($api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$json = curl_exec($ch);
curl_close($ch);
$stats = json_decode($json, true) ?: [];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; }
        .nav-pills .nav-link.active { background: #0d6efd; }
    </style>
</head>
<body class="p-4">
<div class="container">
    <h2 class="mb-4">📊 IndieMa Analytics</h2>

    <ul class="nav nav-pills mb-4">
        <li class="nav-item"><a class="nav-link active" href="?period=1d">Today</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=7d">7 Days</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=15d">15 Days</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=30d">30 Days</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=90d">3 Months</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=1y">1 Year</a></li>
        <li class="nav-item"><a class="nav-link" href="?period=all">All Time</a></li>
    </ul>

    <div class="row">
        <?php foreach ($stats as $s): ?>
        <div class="col-md-6 mb-4">
            <div class="card p-4">
                <h4><?=htmlspecialchars($s['name'])?></h4>
                <span class="badge <?= $s['status']=='ONLINE' ? 'bg-success' : 'bg-danger' ?>"><?= $s['status'] ?></span>
                <hr>
                <p><strong>Clips:</strong> <?= $s['clip_count'] ?></p>
                <p><strong>Current Viewers:</strong> <span class="text-info"><?= $s['viewers'] ?></span></p>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
</div>
</body>
</html>
