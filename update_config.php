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

function setConfigValue($pdo, $key, $value) {
    $stmt = $pdo->prepare("
        INSERT OR REPLACE INTO configuration (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ");
    return $stmt->execute([$key, $value]);
}

function getConfigValue($pdo, $key, $default = null) {
    $stmt = $pdo->prepare("SELECT value FROM configuration WHERE key = ?");
    $stmt->execute([$key]);
    $result = $stmt->fetch(PDO::FETCH_COLUMN);
    return $result !== false ? $result : $default;
}

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $pdo = getDbConnection($db_file);
    
    if (isset($_POST['check_interval_minutes'])) {
        $interval = (int)$_POST['check_interval_minutes'];
        
        // Validate input
        if ($interval >= 1 && $interval <= 1440) {
            if (setConfigValue($pdo, 'check_interval_minutes', $interval)) {
                $_SESSION['message'] = "Configuration updated successfully! New interval: {$interval} minutes";
                $_SESSION['message_type'] = "success";
            } else {
                $_SESSION['message'] = "Failed to update configuration";
                $_SESSION['message_type'] = "error";
            }
        } else {
            $_SESSION['message'] = "Invalid interval value. Must be between 1 and 1440 minutes.";
            $_SESSION['message_type'] = "error";
        }

    } elseif (isset($_POST['update_priority_tags'])) {
        // Handle priority tags update
        $priority_tags = isset($_POST['priority_tags']) ? $_POST['priority_tags'] : [];
        
        // Validate that all priority tags are valid artist tags
        $stmt = $pdo->prepare("SELECT tag_name FROM monitored_tags WHERE is_active = 1");
        $stmt->execute();
        $valid_tags = $stmt->fetchAll(PDO::FETCH_COLUMN);
        
        $invalid_tags = array_diff($priority_tags, $valid_tags);
        if (!empty($invalid_tags)) {
            $_SESSION['message'] = "Invalid priority tags: " . implode(', ', $invalid_tags);
            $_SESSION['message_type'] = "error";
        } else {
            $priority_tags_json = json_encode($priority_tags);
            if (setConfigValue($pdo, 'priority_tags', $priority_tags_json)) {
                $count = count($priority_tags);
                $_SESSION['message'] = "Priority tags updated successfully! {$count} priority tag(s) set.";
                $_SESSION['message_type'] = "success";
            } else {
                $_SESSION['message'] = "Failed to update priority tags";
                $_SESSION['message_type'] = "error";
            }
        }
    } elseif (isset($_POST['add_priority_tag']) && isset($_POST['new_priority_tag'])) {
        // Handle adding a new priority tag
        $new_tag = trim($_POST['new_priority_tag']);
        
        if (empty($new_tag)) {
            $_SESSION['message'] = "Please enter a tag name";
            $_SESSION['message_type'] = "error";
        } else {
            // Validate that the tag exists in monitored_tags
            $stmt = $pdo->prepare("SELECT tag_name FROM monitored_tags WHERE tag_name = ? AND is_active = 1");
            $stmt->execute([$new_tag]);
            if (!$stmt->fetch()) {
                $_SESSION['message'] = "Tag '{$new_tag}' not found in monitored artists";
                $_SESSION['message_type'] = "error";
            } else {
                // Get current priority tags
                $priority_tags_json = getConfigValue($pdo, 'priority_tags', '[]');
                $priority_tags = json_decode($priority_tags_json, true);
                $priority_tags = is_array($priority_tags) ? $priority_tags : [];
                
                // Add new tag if not already present
                if (!in_array($new_tag, $priority_tags)) {
                    $priority_tags[] = $new_tag;
                    $priority_tags_json = json_encode($priority_tags);
                    
                    if (setConfigValue($pdo, 'priority_tags', $priority_tags_json)) {
                        $_SESSION['message'] = "Priority tag '{$new_tag}' added successfully!";
                        $_SESSION['message_type'] = "success";
                    } else {
                        $_SESSION['message'] = "Failed to add priority tag";
                        $_SESSION['message_type'] = "error";
                    }
                } else {
                    $_SESSION['message'] = "Tag '{$new_tag}' is already a priority tag";
                    $_SESSION['message_type'] = "error";
                }
            }
        }
    } elseif (isset($_POST['remove_priority_tag'])) {
        // Handle removing a priority tag (AJAX request)
        $tag_to_remove = $_POST['remove_priority_tag'];
        
        // Get current priority tags
        $priority_tags_json = getConfigValue($pdo, 'priority_tags', '[]');
        $priority_tags = json_decode($priority_tags_json, true);
        $priority_tags = is_array($priority_tags) ? $priority_tags : [];
        
        // Remove the tag
        $priority_tags = array_values(array_diff($priority_tags, [$tag_to_remove]));
        $priority_tags_json = json_encode($priority_tags);
        
        if (setConfigValue($pdo, 'priority_tags', $priority_tags_json)) {
            echo json_encode(['success' => true]);
            exit;
        } else {
            echo json_encode(['success' => false, 'error' => 'Failed to remove priority tag']);
            exit;
        }
    } else {
        $_SESSION['message'] = "No configuration value provided";
        $_SESSION['message_type'] = "error";
    }
} else {
    $_SESSION['message'] = "Invalid request method";
    $_SESSION['message_type'] = "error";
}

// Redirect back to main page
header("Location: index.php");
exit;
?> 