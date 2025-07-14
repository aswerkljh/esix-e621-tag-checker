<?php

$db_file = 'e621_monitor.db';

function getDbConnection($db_file) {
    try {
        $pdo = new PDO("sqlite:$db_file");
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        return $pdo;
    } catch (PDOException $e) {
        http_response_code(500);
        die(json_encode(['error' => 'Database connection failed']));
    }
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['error' => 'Method not allowed']));
}

$artist = $_POST['artist'] ?? null;

if (!$artist) {
    http_response_code(400);
    die(json_encode(['error' => 'Artist parameter required']));
}

try {
    $pdo = getDbConnection($db_file);
    
    try { // Try to add 'seen' column if it doesn't exist (ignore if already exists)
        $pdo->exec("ALTER TABLE monitored_tags ADD COLUMN seen BOOLEAN DEFAULT 0");
    } catch (Exception $e) { // Column might already exist, that's okay
    }
    
    $stmt = $pdo->prepare("UPDATE monitored_tags SET seen = 1 WHERE tag_name = ?");
    $stmt->execute([$artist]);
    
    $updated_count = $stmt->rowCount();
    
    header('Content-Type: application/json');
    echo json_encode([
        'success' => true,
        'artist' => $artist,
        'updated_count' => $updated_count
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    die(json_encode(['error' => 'Database error: ' . $e->getMessage()]));
}
?> 