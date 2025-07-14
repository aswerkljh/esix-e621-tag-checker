# e621 'esix monitor' Artist Tag Monitor

A Python-based monitoring system that tracks new posts on e621.net for specific artist tags, with a simple PHP interface.
Assumes that you know how to operate a webserver and that you have a local folder structure for your porn collection

## Features

- **Automated Monitoring**: Python script runs as a background service checking artists for new posts with configurable delay
- **Priority Tag System**: Guaranteed daily checks for configurable priority tags
- **Clean Web Interface**: Modern, responsive PHP dashboard showing which artists have new posts
- **SQLite Database**: Lightweight storage for tracking post IDs and monitoring history
- **Seen Functionality**: Mark artists as seen to hide them until new posts arrive
- **Optional Folder-Monitoring**: Optional python script to monitor a folder for new artists and add them to the watchlist.

The folder monitor script expects a certain folder structure. Folders should be named after the artist as their exact tag is on e621, including if it has _(artist) appended to it. 

Porn
├─ snowskau
│  └─ subfolders are not processed so does not matter
├─ negiumaya_(artist)
└─ trigaroo
    ├─ Some Comic 1
    └─ Some Comic 2

## Installation

### Prerequisites

- **Python 3.7+** with pip
- **PHP 7.4+** with PDO SQLite extension
- **Web server** (Apache/Nginx)

### Step 1: Download and Setup

1. **Download the project files** to your web directory:
   ```bash
   # Option 1: Clone the repository (if available)
   git clone <repository-url> /var/www/drkt.eu/subdomains/esix
   cd /var/www/drkt.eu/subdomains/esix
   
   # Option 2: Download and extract files manually
   # Place all project files in your web directory
   ```

2. **Set proper permissions**:
   ```bash
   # Make sure the web server can write to the directory
   chmod 755 /var/www/drkt.eu/subdomains/esix
   chown www-data:www-data /var/www/drkt.eu/subdomains/esix
   ```

### Step 2: Install Python Dependencies

1. **Create a virtual environment** (recommended):
   ```bash
   cd /var/www/drkt.eu/subdomains/esix
   python3 -m venv esixmonitor-venv
   source esixmonitor-venv/bin/activate
   ```

2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

   The requirements include:
   - `requests==2.31.0` - HTTP library for API calls
   - `schedule==1.2.0` - Task scheduling
   - `python-dotenv==1.0.0` - Environment variable management

### Step 3: Configure the Monitor

1. **Edit the configuration** in `e621_monitor.py`:
   ```python
   self.config = {
       'e621_api': {
           'base_url': 'https://e621.net',
           'user_agent': 'esix update checker/0.3 (by username: YOUR_USERNAME | email: YOUR_EMAIL)'
       },
       'monitoring': {
           'check_interval_minutes': 30,  # How often to check for new posts
           'max_posts_per_check': 1       # Max posts to fetch per check
       },
       'priority_tags': [
           'snowskau',
           'sterr', 
           'spuydjeks',
           'dark_violet'
           # Add your priority artists here
       ]
   }
   ```

2. **Update the User-Agent** with your e621.net username and email for API compliance.

### Step 4: Set Up Artist Discovery (Optional)

If you have artist folders on another machine (machine 30):

1. **Configure the discovery script** (`artist_discovery.py`) on machine 30
2. **Set up SCP** to push `artists.json` to machine 164:
   ```bash
   # On machine 30, set up a cron job to push artists.json
   scp artists.json user@machine164:/var/www/drkt.eu/subdomains/esix/
   ```

3. **Or manually create** `artists.json`:
   ```json
   {
     "artists": [
       "artist:example1",
       "artist:example2",
       "artist:example3"
     ]
   }
   ```

### OPTIONAL Artist Discovery Script (`artist_discovery.py`)

The `artist_discovery.py` script is an **optional component** that automatically scans your local artist folder structure and generates the `artists.json` file. This script is designed for users who have their art collection organized in folders by artist name.

#### What it does:
- **Scans directories** for artist folders (excluding folders starting with underscore)
- **Generates `artists.json`** with the discovered artist names
- **Pushes the file** to the monitoring machine via SCP
- **Handles folder structure** automatically, so you don't need to manually maintain the artist list

#### Configuration:
The script is currently configured to scan `/srv/nas/Furry/NSFW Furry` on machine 30. You can modify the `directory_path` variable in the script to match your folder structure:

```python
directory_path = "/path/to/your/artist/folders"
```

#### Usage:
```bash
# Run the discovery script
python3 artist_discovery.py

# Set up as a cron job to run periodically
# Example: Run every 6 hours
0 */6 * * * cd /path/to/script && python3 artist_discovery.py
```

#### Manual Alternative:
If you don't save your porn locally or prefer manual control, you can **skip this script entirely** and manually edit `artists.json`, or create it if it does not exist:

```json
{
  "artists": [
    "artist:snowskau",
    "artist:sterr",
    "artist:spuydjeks",
    "negiumaya_(artist)"
  ]
}
```

The monitor will work perfectly fine with a manually curated `artists.json` file. The discovery script is just a convenience for me personally. 

### Step 5: Configure Web Server

1. **Ensure PHP has SQLite support**:
   ```bash
   # Check if PDO SQLite is installed
   php -m | grep pdo
   php -m | grep sqlite
   
   # Install if missing (Ubuntu/Debian)
   sudo apt-get install php-sqlite3
   ```

## Usage

### Starting the Monitor

1. **Test the setup** (run in foreground first):
   ```bash
   cd /var/www/drkt.eu/subdomains/esix
   source esixmonitor-venv/bin/activate  # If using virtual environment
   python3 e621_monitor.py
   ```

2. **Run as background service**:
   ```bash
   # Using nohup
   nohup python3 e621_monitor.py > e621_monitor.log 2>&1 &
   
   # Or using screen
   screen -S e621-monitor
   python3 e621_monitor.py
   # Press Ctrl+A, then D to detach
   ```

3. **Set up as systemd service** (recommended for production):
   ```bash
   # Create service file
   sudo nano /etc/systemd/system/e621-monitor.service
   ```

   Add this content:
   ```ini
   [Unit]
   Description=e621 Artist Tag Monitor
   After=network.target
   
   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/drkt.eu/subdomains/esix
   ExecStart=/var/www/drkt.eu/subdomains/esix/esixmonitor-venv/bin/python e621_monitor.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

   Then enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable e621-monitor
   sudo systemctl start e621-monitor
   sudo systemctl status e621-monitor
   ```

### Accessing the Web Interface

1. **Navigate to your web interface**:
   ```
   http://your-domain.com/index.php
   ```

2. **The interface shows**:
   - **Summary Statistics**: Total monitored artists and artists with new posts
   - **Artist Cards**: Each monitored artist with status indicators
   - **Direct Links**: Click "View Posts" to mark as seen and open artist page on e621.net
   - **Auto-refresh**: Page updates every 5 minutes

### Managing Artists

1. **Add new artists**:
   - Edit `artists.json` and add the artist tag
   - The monitor will automatically pick up changes within 6 hours
   - Or restart the monitor to pick up changes immediately

2. **Mark artists as seen**:
   - Click "View Posts" in the web interface
   - This marks the artist as seen until new posts arrive

3. **Check monitor status**:
   ```bash
   # Check if monitor is running
   ps aux | grep e621_monitor
   
   # Check logs
   tail -f e621_monitor.log
   
   # Check systemd service status
   sudo systemctl status e621-monitor
   ```

## Configuration Options

### Monitor Configuration

Edit the configuration section in `e621_monitor.py`:

```python
self.config = {
    'e621_api': {
        'base_url': 'https://e621.net',
        'user_agent': 'esix update checker/0.3 (by username: YOUR_USERNAME | email: YOUR_EMAIL)'
    },
    'monitoring': {
        'check_interval_minutes': 30,  # This is a fallback, the real setting is stored in the database
        'max_posts_per_check': 1       # Posts to fetch per check, only 1 is needed so do not edit this
    },
    'priority_tags': [
        # This is a fallback, the real setting is stored in the database
    ]
}
```

### Web Interface Configuration

The web interface automatically reads configuration from the database. You can update settings through the web interface or directly in the database.

## Monitoring Logic

### Priority Tags
- Priority tags are checked at least once every 2 days
- If a priority tag hasn't been checked in 2 days, it gets checked immediately
- Priority tags are selected randomly when multiple need checking

### Non-Priority Tags
- Non-priority tags use oldest-checked selection
- The system queries the database for the tag checked longest ago
- This ensures fair distribution across all artists

### Artist Discovery
- New artists are automatically added when found in `artists.json`
- Deleted artists are marked as inactive
- The system handles folder deletions gracefully

## Database Schema

### monitored_tags
- `id`: Primary key
- `tag_name`: Artist tag name (e.g., "artist:example")
- `last_post_id`: Highest post ID seen for this tag
- `last_checked`: Timestamp of last check
- `is_active`: Whether to monitor this tag
- `seen`: Whether the user has marked this artist as seen

### new_posts_log
- `id`: Primary key
- `tag_name`: Artist tag name
- `post_id`: Post ID that was discovered
- `discovered_at`: When the post was first seen

### configuration
- `key`: Configuration key
- `value`: Configuration value
- `updated_at`: When the configuration was last updated

## Troubleshooting

### Common Issues

1. **Database connection errors**:
   ```bash
   # Check file permissions
   ls -la e621_monitor.db
   chmod 644 e621_monitor.db
   chown www-data:www-data e621_monitor.db
   ```

2. **Monitor not starting**:
   ```bash
   # Check Python dependencies
   pip list | grep -E "(requests|schedule|python-dotenv)"
   
   # Check Python version
   python3 --version
   ```

3. **API rate limiting**:
   - Check `e621_monitor.log` for 429 errors
   - Increase check interval in configuration
   - Verify User-Agent is properly set

4. **No new posts detected**:
   ```bash
   # Check if tags exist on e621.net
   curl -H "User-Agent: esix update checker/0.3" "https://e621.net/posts.json?tags=artist:example&limit=1"
   ```

5. **Web interface not loading**:
   ```bash
   # Check PHP SQLite extension
   php -m | grep sqlite
   
   # Check web server logs
   sudo tail -f /var/log/apache2/error.log
   # or
   sudo tail -f /var/log/nginx/error.log
   ```

### Log Files

- `e621_monitor.log`: Python script activity
- Check for errors, API responses, and monitoring status

### Testing

Test the setup by checking the logs for:
- Artist discovery messages
- Priority tag checks
- Oldest-checked tag selection

## Security Considerations

- The monitor only reads public data from e621.net
- No authentication required for the API
- Database contains only post IDs and timestamps
- Web interface shows no sensitive information
- Use proper file permissions to secure the installation

## Performance

- **Lightweight**: SQLite database, minimal resource usage
- **Efficient**: Only checks for new posts, doesn't store images
- **Scalable**: Can monitor hundreds of tags with minimal impact
- **Reliable**: Handles API errors gracefully with retry logic
- **Smart Selection**: Priority tags get guaranteed checks, others use fair distribution

## Contributing

Feel free to submit issues or feature requests. The system is designed to be:

- **Modular**: Easy to extend with new features
- **Configurable**: All settings embedded in Python script
- **Maintainable**: Clean, documented code
- **User-friendly**: Simple setup and usage

## License

This project is licensed under the WTFPL (Do What The Fuck You Want To Public License).

```
            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                    Version 2, December 2004


 Copyright (C) 2025 e621 esix monitor contributors

 Everyone is permitted to copy and distribute verbatim or modified
 copies of this license document, and changing it is allowed as long
 as the name is changed.

            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. You just DO WHAT THE FUCK YOU WANT TO.
```

Use responsibly and respect e621.net's terms of service. 