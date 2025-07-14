#!/usr/bin/env python3
"""
e621.net Artist Tag Monitor

This script monitors e621.net for new posts on specified artist tags
and stores the results in a SQLite database for the PHP web interface.
"""

import json
import sqlite3
import time
import logging
import requests
import schedule
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('e621_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class E621Monitor:
    def __init__(self, db_file='e621_monitor.db'):
        # Configuration
        self.config = {
            'e621_api': {
                'base_url': 'https://e621.net',
                'user_agent': 'esix update checker/0.3 (by username: 089231745aaa | email: esix@drkt.eu)'
            },
            'monitoring': {
                'check_interval_minutes': 30,
                'max_posts_per_check': 1
            },
            'priority_tags': [
                'snowskau',
                'sterr',
                'spuydjeks',
                'dark_violet'
            ]
        }
        
        self.db_file = db_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config['e621_api']['user_agent']
        })
        self.init_database()
    
    def load_artists_from_json(self):
        """Load artists from artists.json file."""
        try:
            with open('artists.json', 'r') as f:
                data = json.load(f)
                return data.get('artists', [])
        except FileNotFoundError:
            logger.error("artists.json not found!")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing artists.json: {e}")
            return []
    
    def init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Create monitored_tags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monitored_tags (
                    id INTEGER PRIMARY KEY,
                    tag_name TEXT UNIQUE NOT NULL,
                    last_post_id INTEGER DEFAULT 0,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    seen BOOLEAN DEFAULT 0
                )
            ''')
            
            # Create new_posts_log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS new_posts_log (
                    id INTEGER PRIMARY KEY,
                    tag_name TEXT NOT NULL,
                    post_id INTEGER NOT NULL,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tag_name, post_id)
                )
            ''')
            
            # Create configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Initialize default configuration values
            cursor.execute('''
                INSERT OR IGNORE INTO configuration (key, value) 
                VALUES ('check_interval_minutes', ?)
            ''', (str(self.config['monitoring']['check_interval_minutes']),))
            
            # Initialize priority tags
            cursor.execute('''
                INSERT OR IGNORE INTO configuration (key, value) 
                VALUES ('priority_tags', ?)
            ''', (json.dumps(self.config['priority_tags']),))
            
            # Load artists from artists.json or fallback to config
            artists = self.load_artists_from_json()
            
            # Insert artists as monitored tags
            for artist in artists:
                cursor.execute('''
                    INSERT OR IGNORE INTO monitored_tags (tag_name) 
                    VALUES (?)
                ''', (artist,))
            
            # Add seen column if it doesn't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE monitored_tags ADD COLUMN seen BOOLEAN DEFAULT 0')
                conn.commit()
                logger.info("Added 'seen' column to existing database")
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            conn.commit()
            logger.info(f"Database initialized with {len(artists)} artists")
    
    def get_config_value(self, key, default=None):
        """Get a configuration value from the database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM configuration WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    
    def set_config_value(self, key, value):
        """Set a configuration value in the database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO configuration (key, value, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, str(value)))
            conn.commit()
    
    def get_latest_posts(self, tag, limit=50):
        """Fetch latest posts for a given tag from e621 API."""
        url = f"{self.config['e621_api']['base_url']}/posts.json"
        params = {
            'tags': tag,
            'limit': limit,
            'page': 1
        }
        
        try:
            response = self.session.get(url, params=params)
            
            # Check for HTTP errors
            if response.status_code == 403:
                logger.error(f"Access denied (403) for {tag} - check User-Agent configuration")
                return []
            elif response.status_code == 429:
                logger.info(f"Rate limited (429) for {tag} - pausing script for 2 hours")
                time.sleep(7200)  # 2 hours = 7200 seconds
                return []
            elif response.status_code != 200:
                logger.error(f"HTTP {response.status_code} error for {tag}: {response.text[:200]}")
                return []
            
            data = response.json()
            posts = data.get('posts', [])
            return posts
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching posts for {tag}: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {tag}: {e}")
            return []
    
    def check_tag_for_new_posts(self, tag):
        """Check a specific tag for new posts and update database."""
        logger.info(f"Checking {tag}")
        
        # Get current last_post_id from database
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT last_post_id FROM monitored_tags WHERE tag_name = ?',
                (tag,)
            )
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"Tag {tag} not found in database")
                return
            
            last_post_id = result[0]
        
        # Fetch latest posts
        posts = self.get_latest_posts(tag, self.config['monitoring']['max_posts_per_check'])
        
        # Always update last_checked timestamp, even if no posts found
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            if not posts:
                # No posts found (could be invalid tag or no posts)
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_checked = CURRENT_TIMESTAMP
                    WHERE tag_name = ?
                ''', (tag,))
                conn.commit()
                return
            
            # Find new posts (posts with ID > last_post_id)
            new_posts = [post for post in posts if post['id'] > last_post_id]
            
            if new_posts:
                # Sort by ID to get the highest
                new_posts.sort(key=lambda x: x['id'])
                highest_id = new_posts[-1]['id']
                
                # Update last_post_id and last_checked
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_post_id = ?, last_checked = CURRENT_TIMESTAMP
                    WHERE tag_name = ?
                ''', (highest_id, tag))
                
                # Log new posts
                for post in new_posts:
                    cursor.execute('''
                        INSERT OR IGNORE INTO new_posts_log (tag_name, post_id)
                        VALUES (?, ?)
                    ''', (tag, post['id']))
                
                # Reset seen flag when new posts are found
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET seen = 0 
                    WHERE tag_name = ?
                ''', (tag,))
                
                conn.commit()
                
                # Check if this is a first-time check (last_post_id was 0)
                if last_post_id == 0:
                    logger.info(f"New artist discovered: {tag} - Found {len(new_posts)} existing posts")
                else:
                    logger.info(f"Found {len(new_posts)} new posts for {tag}")
            else:
                # No new posts found, but update last_checked
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_checked = CURRENT_TIMESTAMP
                    WHERE tag_name = ?
                ''', (tag,))
                conn.commit()
    
    def refresh_artists_from_json(self):
        """Refresh the monitored artists from artists.json."""
        try:
            artists = self.load_artists_from_json()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Get current artists in database
                cursor.execute('SELECT tag_name FROM monitored_tags WHERE is_active = 1')
                current_tags = {row[0] for row in cursor.fetchall()}
                
                # Get new artists from JSON
                new_tags = set(artists)
                
                # Add new artists
                new_artists_added = []
                for tag in new_tags:
                    if tag not in current_tags:
                        cursor.execute('''
                            INSERT OR IGNORE INTO monitored_tags (tag_name) 
                            VALUES (?)
                        ''', (tag,))
                        new_artists_added.append(tag)
                
                # Remove deleted artists (mark as inactive)
                deleted_artists = []
                for tag in current_tags:
                    if tag not in new_tags:
                        cursor.execute('''
                            UPDATE monitored_tags 
                            SET is_active = 0 
                            WHERE tag_name = ?
                        ''', (tag,))
                        deleted_artists.append(tag)
                
                conn.commit()
                
                if new_artists_added:
                    logger.info(f"🎨 Added {len(new_artists_added)} new artists: {', '.join(new_artists_added)}")
                if deleted_artists:
                    logger.info(f"🗑️ Removed {len(deleted_artists)} deleted artists: {', '.join(deleted_artists)}")
                
        except Exception as e:
            logger.error(f"Error refreshing artists from JSON: {e}")
    
    def get_priority_tags_to_check(self):
        """Get priority tags that haven't been checked in the last 24 hours."""
        # Get priority tags from database config
        priority_tags_json = self.get_config_value('priority_tags', json.dumps(self.config['priority_tags']))
        priority_tags = json.loads(priority_tags_json)
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Get priority tags that are active and haven't been checked in 24 hours
            if priority_tags:
                placeholders = ','.join(['?' for _ in priority_tags])
                cursor.execute(f'''
                    SELECT tag_name FROM monitored_tags 
                    WHERE tag_name IN ({placeholders}) 
                    AND is_active = 1 
                    AND (last_checked IS NULL OR last_checked < datetime('now', '-1 day'))
                ''', priority_tags)
                
                priority_tags = [row[0] for row in cursor.fetchall()]
            else:
                priority_tags = []
            
        return priority_tags
    
    def check_oldest_tag(self):
        """Check a monitored tag for new posts, with priority for tags that need daily checks."""
        # First, check if any priority tags need to be checked today
        priority_tags_to_check = self.get_priority_tags_to_check()
        
        if priority_tags_to_check:
            # Check a priority tag that hasn't been checked in 24 hours
            priority_tag = random.choice(priority_tags_to_check)
            self.check_tag_for_new_posts(priority_tag)
            return
        
        # If no priority tags need checking, check the oldest checked tag
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tag_name FROM monitored_tags 
                WHERE is_active = 1 
                ORDER BY last_checked ASC NULLS FIRST
                LIMIT 1
            ''')
            result = cursor.fetchone()
        
        if not result:
            logger.warning("No active tags to monitor")
            return
        
        oldest_tag = result[0]
        self.check_tag_for_new_posts(oldest_tag)
    
    def run_monitor(self):
        """Run the monitoring service."""
        logger.info("Starting e621 monitor service")
        
        # Get check interval from database config
        check_interval = int(self.get_config_value('check_interval_minutes', self.config['monitoring']['check_interval_minutes']))
        
        # Schedule oldest tag checks based on config
        schedule.every(check_interval).minutes.do(self.check_oldest_tag)
        
        # Schedule artist refresh every 6 hours
        schedule.every(6).hours.do(self.refresh_artists_from_json)
        
        # Run initial checks
        self.refresh_artists_from_json()
        self.check_oldest_tag()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

def main():
    """Main entry point."""
    try:
        monitor = E621Monitor()
        monitor.run_monitor()
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main() 