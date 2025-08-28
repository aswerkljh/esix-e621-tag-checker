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
        self.config = {
            'e621_api': {
                'base_url': 'https://e621.net',
                'user_agent': 'esix tag checker/0.4 https://github.com/aswerkljh/esix-e621-tag-checker username:089231745aaa email:esix@drkt.eu'
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monitored_tags (
                    id INTEGER PRIMARY KEY,
                    tag_name TEXT UNIQUE NOT NULL,
                    last_post_id INTEGER DEFAULT 0,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    seen BOOLEAN DEFAULT 0,
                    check_failed BOOLEAN DEFAULT 0
                )
            ''')
            

            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO configuration (key, value) 
                VALUES ('check_interval_minutes', ?)
            ''', (str(self.config['monitoring']['check_interval_minutes']),))
            
            cursor.execute('''
                INSERT OR IGNORE INTO configuration (key, value) 
                VALUES ('priority_tags', ?)
            ''', (json.dumps(self.config['priority_tags']),))
            
            artists = self.load_artists_from_json()

            for artist in artists:
                cursor.execute('''
                    INSERT OR IGNORE INTO monitored_tags (tag_name) 
                    VALUES (?)
                ''', (artist,))
            
            try:
                cursor.execute('ALTER TABLE monitored_tags ADD COLUMN seen BOOLEAN DEFAULT 0')
                conn.commit()
                logger.info("Added 'seen' column to existing database")
            except sqlite3.OperationalError:
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
            
            if response.status_code == 403:
                logger.error(f"Access denied (403) for {tag}")
                return [], 'http_error'
            elif response.status_code == 429:
                logger.info(f"Rate limited (429) for {tag} - pausing script for 2 hours")
                time.sleep(7200)  # 2 hours = 7200 seconds
                return [], 'rate_limited'
            elif response.status_code != 200:
                logger.error(f"HTTP {response.status_code} error for {tag}: {response.text[:200]}")
                return [], 'http_error'
            
            data = response.json()
            posts = data.get('posts', [])
            return posts, None
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching posts for {tag}: {e}")
            return [], 'request_error'
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {tag}: {e}")
            return [], 'json_error'
    
    def check_tag_for_new_posts(self, tag):
        """Check a specific tag for new posts and update database."""
        #logger.info(f"Checking {tag}")
        
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
            
        #logger.info(f"Last post ID for {tag}: {last_post_id} (type: {type(last_post_id)})")
        
        posts, error_type = self.get_latest_posts(tag, self.config['monitoring']['max_posts_per_check'])
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            if error_type:
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_checked = CURRENT_TIMESTAMP, check_failed = 1
                    WHERE tag_name = ?
                ''', (tag,))
                conn.commit()
                return
            
            if not posts:
                # It is marked as check_failed because it could indicate the tag is simply wrong, ie missing _(artist)
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_checked = CURRENT_TIMESTAMP, check_failed = 1
                    WHERE tag_name = ?
                ''', (tag,))
                conn.commit()
                return
            
            cursor.execute('''
                UPDATE monitored_tags 
                SET check_failed = 0
                WHERE tag_name = ?
            ''', (tag,))
            
            if posts:
                highest_id = max(post['id'] for post in posts)
                
            new_posts = [post for post in posts if post['id'] > last_post_id]
            
            if posts:
                #logger.info(f"Posts returned for {tag}: {[post['id'] for post in posts]}")
                #logger.info(f"New posts found for {tag}: {[post['id'] for post in new_posts]}")
                
                # Always update the last_post_id to the current highest available
                cursor.execute('''
                    UPDATE monitored_tags 
                    SET last_post_id = ?, last_checked = CURRENT_TIMESTAMP
                    WHERE tag_name = ?
                ''', (highest_id, tag))
            

                
                if new_posts:
                    cursor.execute('''
                        UPDATE monitored_tags 
                        SET seen = 0 
                        WHERE tag_name = ?
                    ''', (tag,))
                
                conn.commit()
                
                if last_post_id == 0:
                    #logger.info(f"New artist discovered: {tag}")
                elif new_posts:
                    #logger.info(f"Found new posts for {tag}")
                elif highest_id != last_post_id:
                    #logger.info(f"Updated last_post_id for {tag} from {last_post_id} to {highest_id} (API returned different posts)")
            else:
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
                
                cursor.execute('SELECT tag_name FROM monitored_tags')
                current_tags = {row[0] for row in cursor.fetchall()}
                
                new_tags = set(artists)
                
                new_artists_added = []
                for tag in new_tags:
                    if tag not in current_tags:
                        cursor.execute('''
                            INSERT OR IGNORE INTO monitored_tags (tag_name) 
                            VALUES (?)
                        ''', (tag,))
                        new_artists_added.append(tag)
                
                # If an artist is deleted from artists.json, it will be completely deleted from the database
                deleted_artists = []
                for tag in current_tags:
                    if tag not in new_tags:
                        cursor.execute('DELETE FROM monitored_tags WHERE tag_name = ?', (tag,))
                        deleted_artists.append(tag)
                
                conn.commit()
                
                if new_artists_added:
                    logger.info(f"Added {len(new_artists_added)} new artists: {', '.join(new_artists_added)}")
                if deleted_artists:
                    logger.info(f"Completely removed {len(deleted_artists)} deleted artists: {', '.join(deleted_artists)}")
                
        except Exception as e:
            logger.error(f"Error refreshing artists from JSON: {e}")
    
    def get_priority_tags_to_check(self):
        """Get priority tags that haven't been checked in the last 24 hours."""
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
                ORDER BY last_checked ASC NULLS FIRST
                LIMIT 1
            ''')
            result = cursor.fetchone()
        
        if not result:
            logger.warning("No active tags to monitor")
            return
        
        oldest_tag = result[0]
        self.check_tag_for_new_posts(oldest_tag)
    
    def check_config_updates(self):
        """Check for configuration updates and reschedule jobs if needed."""
        current_interval = int(self.get_config_value('check_interval_minutes', self.config['monitoring']['check_interval_minutes']))
        
        if hasattr(self, '_last_check_interval') and self._last_check_interval != current_interval:
            logger.info(f"Check interval updated from {self._last_check_interval} to {current_interval} minutes")
            
            schedule.clear()
            schedule.every(current_interval).minutes.do(self.check_oldest_tag)
            schedule.every(6).hours.do(self.refresh_artists_from_json)
            schedule.every(10).minutes.do(self.check_config_updates)  # Re-add config check
            
            self._last_check_interval = current_interval
        elif not hasattr(self, '_last_check_interval'):
            self._last_check_interval = current_interval
            logger.info(f"Initial check interval set to {current_interval} minutes")
    
    def run_monitor(self):
        """Run the monitoring service."""
        logger.info("Starting esix...")

        check_interval = int(self.get_config_value('check_interval_minutes', self.config['monitoring']['check_interval_minutes']))
        logger.info(f"Using check interval of {check_interval} minutes")

        schedule.every(check_interval).minutes.do(self.check_oldest_tag)

        schedule.every(12).hours.do(self.refresh_artists_from_json)

        schedule.every(30).minutes.do(self.check_config_updates)

        self.refresh_artists_from_json()
        self.check_oldest_tag()
        
        while True:
            schedule.run_pending()
            time.sleep(60)

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