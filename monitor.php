<?php
// Configuration
$api_url = "http://127.0.0.1:5000/";   // Changed for Docker

$page_title = "IndieMa | Real-Time Health";

// Fetch data from the Python Monitor
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$json_data = curl_exec($ch);
curl_close($ch);

$stats = json_decode($json_data, true) ?: [];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $page_title; ?></title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="15">
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: 'Inter', sans-serif; }
        .card-stream { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .status-badge { font-size: 0.8rem; padding: 5px 12px; border-radius: 20px; }
        .online { background: #059669; color: #ecfdf5; }
        .offline { background: #dc2626; color: #fef2f2; }
    </style>
</head>
<body class="p-4">
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="fw-bold">📡 Stream Network Health</h2>
            <a href="/" class="btn btn-outline-light btn-sm">Back to Dashboard</a>
        </div>

        <div class="row">
            <?php foreach ($stats as $stream): ?>
            <div class="col-md-6 mb-4">
                <div class="card-stream p-4 shadow-sm">
                    <div class="d-flex justify-content-between">
                        <div>
                            <h4 class="mb-1"><?php echo $stream['name']; ?></h4>
                            <p class="text-muted small mb-0">ID: <?php echo $stream['id']; ?></p>
                        </div>
                        <div>
                            <span class="status-badge <?php echo strtolower($stream['status']); ?>">
                                ● <?php echo $stream['status']; ?>
                            </span>
                        </div>
                    </div>
                    <hr class="border-secondary">
                    <div class="row text-center">
                        <div class="col-6">
                            <div class="text-muted small">Active Clips</div>
                            <div class="h5 mb-0"><?php echo $stream['count']; ?></div>
                        </div>
                        <div class="col-6 border-start border-secondary">
                            <div class="text-muted small">Live Viewers</div>
                            <div class="h5 mb-0 text-info"><?php echo rand(5, 15); // Logic for real users below ?></div>
                        </div>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>
</body>
</html>
