# e621 'esix monitor' Artist Tag Monitor

A Python-based monitoring system for Linux that tracks new posts on e621.net for specific artist tags, with a simple PHP interface.

![Logo](./preview.png?)

Assumes that you know how to operate a webserver. Does not download anything for you or on your behalf.

## Features

- **Automated Monitoring**: Python script runs as a background service checking artists for new posts with configurable delay
- **Priority Tag System**: Guaranteed daily checks for configurable priority tags
- **Clean Web Interface**: Modern, responsive PHP dashboard showing which artists have new posts
- **SQLite Database**: Lightweight storage for tracking post IDs and monitoring history
- **Seen Functionality**: Mark artists as seen to hide them until new posts arrive
- **Optional Folder-Monitoring**: Optional python script to monitor a folder for new artists and add them to the watchlist.

The folder monitor script expects a certain folder structure. Folders should be named after the artist as their exact tag is on e621, including if it has _(artist) appended to it. 

```
Porn
├─ snowskau
│  └─ subfolders are not processed so does not matter
├─ negiumaya_(artist)
└─ trigaroo
    ├─ Some Comic 1
    └─ Some Comic 2
```

## Installation

### Prerequisites

- **Python 3.7+** with pip
- **PHP 7.4+** with PDO SQLite extension
- **Web server** (Apache/Nginx)

### Step 1: Download and Setup

1. **Download the project files** to your web directory:
   ```bash
   cd /var/www/html
   git clone https://github.com/aswerkljh/esix-e621-tag-checker
   ```

### Step 2: Install Python Dependencies

2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

### Step 3: Configure the Monitor

1. **Edit the configuration** in `e621_monitor.py`:
```python
self.config = {
    'e621_api': {
        'base_url': 'https://e621.net',
        'user_agent': 'esix update checker/0.3 (by username: YOUR_USERNAME | email: YOUR_EMAIL)'
    },
    'monitoring': {
        'check_interval_minutes': 30,  # This is a fallback, the real setting is stored in the database
        'max_posts_per_check': 1       # Posts to fetch per check, only 1 is needed so do not edit this     TODO: remove
    },
    'priority_tags': [
        # This is a fallback, the real setting is stored in the database
    ]
}
```

2. **Update the User-Agent** with your e621.net username for API compliance.

3. **Populate with tags** in `artists.json`:
```json
{
  "artists": [
    "snowskau",
    "sterr",
    "spuydjeks",
    "negiumaya_(artist)"
  ]
}
```

The monitor will work perfectly fine with a manually curated `artists.json` file. The discovery script is just a convenience for me personally. 

### Step 4: Configure Web Server

1. **Ensure PHP has SQLite support**:
   ```bash
   # Check if PDO SQLite is installed
   if ! $(php -m | grep -E '^pdo$' >/dev/null) || ! $(php -m | grep -E '^sqlite$' >/dev/null); then
      # Install if missing (Ubuntu/Debian)
      sudo apt-get install php-sqlite3
   fi
   ```

### Managing Artists

1. **Add new artists**:
   - Edit `artists.json` and add the artist tag
   - The monitor will automatically pick up changes within 6 hours
   - Or restart the monitor to pick up changes immediately

2. **Mark artists as seen**:
   - Click "View Posts" in the web interface (not middle-mouse click)
   - This marks the artist as seen until new posts arrive


## Monitoring Logic

### Priority Tags
- Priority tags are checked at least once every 24 hours
- If a priority tag hasn't been checked in 24 hours, it gets checked next
- If multiple priority tags are queued at the same time, the next is chosen randomly.

### Non-Priority Tags
- Non-priority tags are checked oldest-first
- The top of the webpage shows how long it will take to check every tag at the current check interval

## Security Considerations

- The monitor only reads public data from e621.net
- No authentication required for the API
- Database contains only post IDs, timestamps and some settings
- Web interface shows no sensitive information except what you're into, I guess
- If deployed on a domain, consider limiting access with authentication or some such


## Contributing

Feel free to submit issues. I probably won't take feature requests, but shoot your shot king.

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

Use responsibly and respect e621.net's terms of service. https://e621.net/help/api
