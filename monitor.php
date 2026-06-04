<?php
$api_url = "http://127.0.0.1:5001/api/stats";
$ch = curl_init($api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 6);
$json = curl_exec($ch);
curl_close($ch);

$stats = json_decode($json, true) ?: [];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa | Real-Time Health</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="20">
    <style>
        body { background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; border: none; }
        .online { background: #059669; color: white; }
        .offline { background: #dc2626; color: white; }
    </style>
</head>
<body class="p-4">
    <div class="container">
        <h2 class="mb-4">📡 Stream Network Health</h2>
        
        <div class="row">
            <?php foreach ($stats as $s): ?>
            <div class="col-md-6 mb-4">
                <div class="card p-4">
                    <div class="d-flex justify-content-between">
                        <h4><?=htmlspecialchars($s['name'])?></h4>
                        <span class="badge <?= $s['status']=='ONLINE' ? 'online' : 'offline' ?>"><?= $s['status'] ?></span>
                    </div>
                    <hr>
                    <div class="row text-center">
                        <div class="col-6">
                            <small>Clips</small><br>
                            <strong><?= $s['clip_count'] ?></strong>
                        </div>
                        <div class="col-6">
                            <small>Live Viewers</small><br>
                            <strong class="text-info"><?= $s['viewers'] ?></strong>
                        </div>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>
</body>
</html>
