<?php
session_start();
$db_file = 'e621_monitor.db';

function getDbConnection($db_file) {
    try {
        $pdo = new PDO("sqlite:$db_file");
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        return $pdo;
    } catch (PDOException $e) {
        die("Database connection failed: " . $e->getMessage());
    }
}

function getArtistsWithNewPosts($pdo) {
    $stmt = $pdo->prepare("
        SELECT DISTINCT mt.tag_name, mt.last_checked
        FROM monitored_tags mt
        WHERE mt.is_active = 1
        AND mt.seen = 0
        AND EXISTS (
            SELECT 1 FROM new_posts_log npl 
            WHERE npl.tag_name = mt.tag_name 
        )
        ORDER BY mt.tag_name
    ");
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

function getTotalArtists($pdo) {
    $stmt = $pdo->prepare("
        SELECT COUNT(*) as total
        FROM monitored_tags mt
        WHERE mt.is_active = 1
    ");
    $stmt->execute();
    $result = $stmt->fetch(PDO::FETCH_ASSOC);
    return $result['total'];
}

function getArtistsWithNoPosts($pdo) {
    $stmt = $pdo->prepare("
        SELECT mt.tag_name, mt.last_checked
        FROM monitored_tags mt
        WHERE mt.is_active = 1
        AND mt.last_post_id = 0
        AND mt.last_checked IS NOT NULL
        ORDER BY mt.last_checked DESC
    ");
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

function getConfigValue($pdo, $key, $default = null) {
    $stmt = $pdo->prepare("SELECT value FROM configuration WHERE key = ?");
    $stmt->execute([$key]);
    $result = $stmt->fetch(PDO::FETCH_ASSOC);
    return $result ? $result['value'] : $default;
}

function setConfigValue($pdo, $key, $value) {
    $stmt = $pdo->prepare("
        INSERT OR REPLACE INTO configuration (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ");
    return $stmt->execute([$key, $value]);
}

function calculateTimeToCheckAllArtists($pdo, $total_artists) {
    // Get check interval from database
    $check_interval_minutes = (int)getConfigValue($pdo, 'check_interval_minutes', 30);
    
    // Calculate total time in minutes
    $total_minutes = $total_artists * $check_interval_minutes;
    
    // Round to nearest hour
    $total_hours = round($total_minutes / 60);
    
    // Convert to days and hours
    $days = floor($total_hours / 24);
    $hours = $total_hours % 24;
    
    // Format the result
    $parts = [];
    if ($days > 0) {
        $parts[] = $days . ' day' . ($days > 1 ? 's' : '');
    }
    if ($hours > 0 || empty($parts)) {
        $parts[] = $hours . ' hour' . ($hours > 1 ? 's' : '');
    }
    
    return implode(', ', $parts);
}

function getPriorityTags($pdo) {
    $priority_tags_json = getConfigValue($pdo, 'priority_tags', '[]');
    $priority_tags = json_decode($priority_tags_json, true);
    return is_array($priority_tags) ? $priority_tags : [];
}

function getAllActiveArtists($pdo) {
    $stmt = $pdo->prepare("
        SELECT tag_name 
        FROM monitored_tags 
        WHERE is_active = 1 
        ORDER BY tag_name
    ");
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_COLUMN);
}

// Get data
$pdo = getDbConnection($db_file);
$artists_with_new_posts = getArtistsWithNewPosts($pdo);
$artists_with_no_posts = getArtistsWithNoPosts($pdo);
$total_artists = getTotalArtists($pdo);
$time_to_check_all = calculateTimeToCheckAllArtists($pdo, $total_artists);
$current_interval = getConfigValue($pdo, 'check_interval_minutes', 30);
$priority_tags = getPriorityTags($pdo);
$all_artists = getAllActiveArtists($pdo);
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>e621 Artist Monitor</title>
    <style>
        body {
            background-color:#1c1c1c;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 10px;
            color: #333;
            font-size: 14px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 16px;
            text-align: center;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 16px;
            text-align: center;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.3em;
            font-weight: 500;
        }
        
        .header-stats {
            display: flex;
            gap: 20px;
            font-size: 0.8em;
            opacity: 0.9;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .content {
            padding: 12px 16px;
        }
        
        .artist-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .artist-item {
            padding: 8px 12px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background-color 0.15s ease;
        }
        
        .artist-name {
            font-weight: 500;
            color: #333;
            font-size: 1.5em;
        }
        
        .artist-item:hover {
            background-color: #f8f9fa;
        }
        
        .artist-item:last-child {
            border-bottom: none;
        }
        
        .artist-name {
            font-weight: 500;
            color: #333;
            font-size: 0.95em;
        }
        
        .artist-link {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 6px 12px;
            font-size: 0.8em;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            width: 140px;
            text-align: center;
            display: inline-block;
        }
        
        .artist-link:hover {
            transform: translateX(-3px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        
        .artist-link.clicked {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
            color: white;
        }
        
        .no-posts {
            text-align: center;
            color: #666;
            padding: 30px 16px;
            font-style: italic;
            font-size: 0.9em;
        }
        
        .section-title {
            font-size: 1.1em;
            font-weight: 600;
            color: #333;
            margin: 20px 0 10px 0;
            padding-bottom: 5px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .empty-artist-item {
            padding: 6px 12px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: #f8f9fa;
            opacity: 0.8;
        }
        
        .empty-artist-name {
            font-weight: 500;
            color: #666;
            font-size: 0.9em;
        }
        
        .empty-artist-time {
            font-size: 0.75em;
            color: #999;
        }
        
        .empty-artist-link {
            background: #6c757d;
            color: white;
            text-decoration: none;
            padding: 4px 8px;
            font-size: 0.7em;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            width: 100px;
            text-align: center;
            display: inline-block;
        }
        
        .empty-artist-link:hover {
            background: #5a6268;
            transform: translateX(-2px);
        }
        
        .settings-section {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid #e9ecef;
        }
        
        .settings-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 0.8em;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .settings-button:hover {
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .settings-note {
            font-size: 0.8em;
            color: #666;
            margin-left: 10px;
        }
        
        .setting-group {
            margin-bottom: 25px;
        }
        
        .setting-group h4 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 1em;
        }
        
        .setting-description {
            font-size: 0.85em;
            color: #666;
            margin: 0 0 15px 0;
        }
        
        .priority-tags-container {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            background: white;
            margin-bottom: 15px;
            border-radius: 4px;
        }
        
        .priority-tag-item {
            display: flex;
            align-items: center;
            padding: 5px 0;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .priority-tag-item:hover {
            background-color: #f8f9fa;
        }
        
        .priority-tag-item input[type="checkbox"] {
            margin-right: 8px;
        }
        
        .priority-tag-item .artist-name {
            color: #333;
        }
        
        .current-priority-tags {
            margin-bottom: 20px;
        }
        
        .current-priority-tags h5 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 0.9em;
        }
        
        .priority-tags-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 10px;
            background: white;
            border: 1px solid #ddd;
        }
        
        .priority-tag-button {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 12px;
            font-size: 0.85em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }
        
        .priority-tag-button:hover {
            background: #dc3545;
        }
        
        .priority-tag-button:hover::after {
            position: absolute;
            top: 50%;
            left: 50%;
            font-size: 1.2em;
            font-weight: bold;
            color: white;
            text-shadow: 0 0 4px rgba(0,0,0,0.5);
        }
        
        .no-priority-tags {
            color: #666;
            font-style: italic;
            margin: 10px 0;
        }
        
        .add-priority-section {
            margin-top: 15px;
        }
        
        .add-priority-section h5 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 0.9em;
        }
        

        
        .message {
            padding: 10px 15px;
            margin-bottom: 15px;
            font-size: 0.9em;
        }
        
        .message.success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .message.error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .message.info {
            background-color: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>e621 New Posts</h1>
            <div class="header-stats">
                <div class="stat-item">
                    <span><?php echo count($artists_with_new_posts); ?> artists with new posts</span>
                </div>
                <div class="stat-item">
                    <span><?php echo $total_artists; ?> artists monitored</span>
                </div>
                <div class="stat-item">
                    <span>Time to check all: <?php echo $time_to_check_all; ?></span>
                </div>
            </div>
        </div>
        
        <div class="content">
            <?php if (isset($_SESSION['message'])): ?>
                <div class="message <?php echo $_SESSION['message_type'] ?? 'info'; ?>">
                    <?php echo htmlspecialchars($_SESSION['message']); ?>
                </div>
                <?php 
                // Clear the message after displaying it
                unset($_SESSION['message']);
                unset($_SESSION['message_type']);
                ?>
            <?php endif; ?>
            
            <div class="section-title">Artist with new posts</div>
            <?php if (empty($artists_with_new_posts)): ?>
                <div class="no-posts">
                    There are no new posts! Thank dog.<br>
                </div>
            <?php else: ?>
                <ul class="artist-list">
                    <?php foreach ($artists_with_new_posts as $artist): ?>
                        <li class="artist-item">
                            <div>
                                <span class="artist-name">
                                    <?php echo htmlspecialchars(str_replace('artist:', '', $artist['tag_name'])); ?>
                                </span>
                                <br>
                                <span class="empty-artist-time">
                                    Last checked: <?php 
                                        $utc = new DateTimeZone('UTC');
                                        $berlin = new DateTimeZone('Europe/Berlin');
                                        $last_checked = new DateTime($artist['last_checked'], $utc);
                                        $last_checked->setTimezone($berlin);
                                        $now = new DateTime('now', $berlin);
                                        $diff = $now->diff($last_checked);
                                        if ($diff->days > 0) {
                                            echo $diff->days . ' day' . ($diff->days > 1 ? 's' : '') . ' ago';
                                        } elseif ($diff->h > 0) {
                                            echo $diff->h . ' hour' . ($diff->h > 1 ? 's' : '') . ' ago';
                                        } elseif ($diff->i > 0) {
                                            echo $diff->i . ' minute' . ($diff->i > 1 ? 's' : '') . ' ago';
                                        } else {
                                            echo 'Just now';
                                        }
                                    ?>
                                </span>
                            </div>
                            <a href="https://e621.net/posts?tags=<?php echo urlencode($artist['tag_name']); ?>" 
                               class="artist-link" target="_blank"
                               onclick="markAsSeen('<?php echo htmlspecialchars($artist['tag_name']); ?>', this, this.href); return false;">
                                View Posts
                            </a>
                        </li>
                    <?php endforeach; ?>
                </ul>
            <?php endif; ?>
            
            <?php if (!empty($artists_with_no_posts)): ?>
                <div class="section-title">Checks Pending / No Posts</div>
                <ul class="artist-list">
                    <?php foreach ($artists_with_no_posts as $artist): ?>
                        <li class="empty-artist-item">
                            <div>
                                <span class="empty-artist-name">
                                    <?php echo htmlspecialchars(str_replace('artist:', '', $artist['tag_name'])); ?>
                                </span>
                                <br>
                                <span class="empty-artist-time">
                                    Last checked: <?php 
                                        $utc = new DateTimeZone('UTC');
                                        $berlin = new DateTimeZone('Europe/Berlin');
                                        $last_checked = new DateTime($artist['last_checked'], $utc);
                                        $last_checked->setTimezone($berlin);
                                        $now = new DateTime('now', $berlin);
                                        $diff = $now->diff($last_checked);
                                        if ($diff->days > 0) {
                                            echo $diff->days . ' day' . ($diff->days > 1 ? 's' : '') . ' ago';
                                        } elseif ($diff->h > 0) {
                                            echo $diff->h . ' hour' . ($diff->h > 1 ? 's' : '') . ' ago';
                                        } elseif ($diff->i > 0) {
                                            echo $diff->i . ' minute' . ($diff->i > 1 ? 's' : '') . ' ago';
                                        } else {
                                            echo 'Just now';
                                        }
                                    ?>
                                </span>
                            </div>
                            <a href="https://e621.net/posts?tags=<?php echo urlencode($artist['tag_name']); ?>" 
                               class="empty-artist-link" target="_blank">
                                Check on e621
                            </a>
                        </li>
                    <?php endforeach; ?>
                </ul>
            <?php endif; ?>
            
            <div class="section-title">Settings</div>
            <div class="settings-section">
                <div class="setting-group">
                    <h4>Check Interval</h4>
                    <form method="POST" action="update_config.php" style="display: inline;">
                        <label for="check_interval">Check Interval (minutes):</label>
                        <input type="number" id="check_interval" name="check_interval_minutes" 
                               value="<?php echo $current_interval; ?>" min="1" max="1440" style="width: 80px; margin: 0 10px;">
                        <button type="submit" class="settings-button">Update</button>
                    </form>
                    <span class="settings-note">Current: <?php echo $current_interval; ?> minutes</span>
                </div>
                
                <div class="setting-group">
                    <h4>Priority Tags</h4>
                    
                    <?php if (!empty($priority_tags)): ?>
                        <div class="current-priority-tags">
                            <div class="priority-tags-buttons">
                                <?php foreach ($priority_tags as $tag): ?>
                                    <button class="priority-tag-button" onclick="removePriorityTag('<?php echo htmlspecialchars($tag); ?>', this)">
                                        <?php echo htmlspecialchars(str_replace('artist:', '', $tag)); ?>
                                    </button>
                                <?php endforeach; ?>
                            </div>
                        </div>
                    <?php else: ?>
                        <p class="no-priority-tags">No priority tags set.</p>
                    <?php endif; ?>
                    
                    <div class="add-priority-section">
                        <form method="POST" action="update_config.php" style="display: flex; align-items: center; gap: 10px;">
                            <input type="text" name="new_priority_tag" placeholder="Add priority tag (e.g., snowskau)" 
                                   style="flex: 1; padding: 6px 10px; border: 1px solid #ddd;">
                            <button type="submit" name="add_priority_tag" class="settings-button">Add</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function markAsSeen(artist, linkElement, url) {
            // Visual feedback - mark button as clicked
            linkElement.classList.add('clicked');
            linkElement.textContent = 'Marked as Seen';
            
            // Open the link in a new tab
            window.open(url, '_blank');
            
            // Send request to mark as seen
            fetch('mark_seen.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'artist=' + encodeURIComponent(artist)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Marked as seen:', artist);
                } else {
                    console.error('Failed to mark as seen:', data.error);
                    // Revert visual feedback on error
                    linkElement.classList.remove('clicked');
                    linkElement.textContent = 'View Posts';
                }
            })
            .catch(error => {
                console.error('Error marking as seen:', error);
                // Revert visual feedback on error
                linkElement.classList.remove('clicked');
                linkElement.textContent = 'Open Artist on e621';
            });
        }
        


        function removePriorityTag(tag, buttonElement) {
            if (confirm('Are you sure you want to remove this priority tag?')) {
                // Send request to remove priority tag
                fetch('update_config.php', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'remove_priority_tag=' + encodeURIComponent(tag)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Priority tag removed:', tag);
                        // Remove the button from DOM
                        buttonElement.remove();
                        // Check if no more priority tags and show "No priority tags set" message
                        const priorityTagsButtons = document.querySelector('.priority-tags-buttons');
                        if (priorityTagsButtons && priorityTagsButtons.children.length === 0) {
                            location.reload(); // Reload to show "No priority tags set" message
                        }
                    } else {
                        console.error('Failed to remove priority tag:', data.error);
                        alert('Failed to remove priority tag: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error removing priority tag:', error);
                    alert('Error removing priority tag: ' + error);
                });
            }
        }
    </script>
</body>
</html> 