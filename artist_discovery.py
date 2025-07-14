#!/usr/bin/env python3
"""
Artist Discovery Script for NAS where porn is stored
Scans directory for artist folders and creates artists.json
"""

import os
import json
import sys
from pathlib import Path

def discover_artists(directory_path):
    """Scan directory for artist folders, excluding underscore-prefixed ones."""
    artists = []
    
    try:
        # Get all directories in the specified path
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            
            # Only process directories
            if os.path.isdir(item_path):
                # Filter out folders starting with underscore
                if not item.startswith('_'):
                    artists.append(item)
        
        # Sort alphabetically for consistency
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
    """Push artists.json to machine 164 via SCP."""
    try:
        import subprocess
        
        # SCP command to copy file to 164
        cmd = [
            'scp', 
            json_file, 
            'user@2a05:f6c7:8321::164:/var/www/drkt.eu/subdomains/esix/artists.json'
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
    # Hardcoded directory path
    directory_path = "/srv/nas/Furry/NSFW Furry"
    
    print(f"Scanning directory: {directory_path}")
    
    # Discover artists
    artists = discover_artists(directory_path)
    
    if not artists:
        print("No artists found or error occurred")
        sys.exit(1)
    
    print(f"Found {len(artists)} artists:")
    for artist in artists:
        print(f"  - {artist}")
    
    # Save to JSON
    if save_artists_json(artists):
        # Push to 164
        if push_to_164():
            print("Artist discovery completed successfully")
        else:
            print("Failed to push to 164, but artists.json was created locally")
    else:
        print("Failed to save artists.json")
        sys.exit(1)

if __name__ == "__main__":
    main() 