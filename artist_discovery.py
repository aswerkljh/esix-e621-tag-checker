#!/usr/bin/env python3

import os
import json
import sys
from pathlib import Path

def discover_artists(directory_path):
    """Scan directory for artist folders, excluding underscore-prefixed ones."""
    artists = []
    
    try:
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            
            if os.path.isdir(item_path):
                if not item.startswith('_'):
                    artists.append(item)
        
        artists.sort()
        
        return artists
        
    except Exception as e:
        print(f"Error scanning directory {directory_path}: {e}")
        return []

def save_artists_json(artists, output_file='artists.json'):
    """Save artists list to JSON file."""
    try:
        data = {
            'artists': artists,
            'last_updated': str(Path().cwd()),
            'total_count': len(artists)
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(artists)} artists to {output_file}")
        return True
        
    except Exception as e:
        print(f"Error saving to {output_file}: {e}")
        return False

def push_to_164(json_file='artists.json'):
    """Push artists.json to web server via SCP."""
    try:
        import subprocess
        
        cmd = [
            'scp', 
            json_file, 
            'user@ip:/var/www/drkt.eu/subdomains/esix/artists.json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Successfully pushed {json_file} to machine 164")
            return True
        else:
            print(f"Error pushing to 164: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error in SCP transfer: {e}")
        return False

def main():
    """Main function to discover and push artists."""
    directory_path = "/srv/nas/Furry/NSFW Furry"
    
    print(f"Scanning directory: {directory_path}")
    
    artists = discover_artists(directory_path)
    
    if not artists:
        print("No artists found or error occurred")
        sys.exit(1)
    
    print(f"Found {len(artists)} artists:")
    for artist in artists:
        print(f"  - {artist}")
    
    if save_artists_json(artists):
        if push_to_164():
            print("Artist discovery completed successfully")
        else:
            print("Failed to push to web server, but artists.json was created locally")
    else:
        print("Failed to save artists.json")
        sys.exit(1)

if __name__ == "__main__":
    main() 