#!/usr/bin/env python3
"""
Batch Processing Script for Gradle Migration

This script helps you process large numbers of repositories in batches
to avoid overwhelming system resources.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List
import subprocess
import json

def load_repositories_from_file(file_path: str) -> List[str]:
    """Load repository URLs from a file"""
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)

def process_batch(repos: List[str], batch_size: int, artifactory_config: dict, 
                  commit_message: str, delay_between_batches: int = 30):
    """Process repositories in batches"""
    total_repos = len(repos)
    processed = 0
    
    print(f"Processing {total_repos} repositories in batches of {batch_size}")
    
    for i in range(0, total_repos, batch_size):
        batch = repos[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_repos + batch_size - 1) // batch_size
        
        print(f"\nBatch {batch_num}/{total_batches}: Processing {len(batch)} repositories")
        
        # Create temporary file for this batch
        batch_file = f"batch_{batch_num}.txt"
        with open(batch_file, 'w') as f:
            for repo in batch:
                f.write(repo + '\n')
        
        # Run migration for this batch
        cmd = [
            sys.executable, 'gradle_artifactory_migrator.py',
            '--repos-file', batch_file,
            '--commit-message', commit_message,
            '--artifactory-url', artifactory_config['url'],
            '--artifactory-repo-key', artifactory_config['repo_key'],
            '--artifactory-username', artifactory_config['username'],
            '--artifactory-password', artifactory_config['password'],
            '--max-workers', str(min(batch_size, 20)),
            '--report-file', f'batch_{batch_num}_report.txt'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Batch {batch_num} completed successfully")
            else:
                print(f"❌ Batch {batch_num} failed: {result.stderr}")
        finally:
            # Clean up batch file
            if os.path.exists(batch_file):
                os.remove(batch_file)
        
        processed += len(batch)
        print(f"Progress: {processed}/{total_repos} repositories processed")
        
        # Wait between batches (except for the last batch)
        if i + batch_size < total_repos:
            print(f"Waiting {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_seconds)

def load_artifactory_config() -> dict:
    """Load Artifactory configuration from environment or config file"""
    config = {
        'url': os.getenv('ARTIFACTORY_URL'),
        'repo_key': os.getenv('ARTIFACTORY_REPO_KEY'),
        'username': os.getenv('ARTIFACTORY_USERNAME'),
        'password': os.getenv('ARTIFACTORY_PASSWORD')
    }
    
    # Check if all required config is present
    if not all(config.values()):
        print("Error: Missing Artifactory configuration")
        print("Please set the following environment variables:")
        print("- ARTIFACTORY_URL")
        print("- ARTIFACTORY_REPO_KEY")
        print("- ARTIFACTORY_USERNAME")
        print("- ARTIFACTORY_PASSWORD")
        sys.exit(1)
    
    return config

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python batch_processor.py <repos_file> [batch_size] [commit_message]")
        print("Example: python batch_processor.py repos.txt 20 \"Migrate to Artifactory\"")
        sys.exit(1)
    
    repos_file = sys.argv[1]
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    commit_message = sys.argv[3] if len(sys.argv) > 3 else "Migrate from Nexus to Artifactory"
    
    # Load repositories
    repos = load_repositories_from_file(repos_file)
    print(f"Loaded {len(repos)} repositories from {repos_file}")
    
    # Load Artifactory configuration
    artifactory_config = load_artifactory_config()
    
    # Process in batches
    process_batch(repos, batch_size, artifactory_config, commit_message)
    
    print("\nBatch processing completed!")
    print("Check individual batch reports for detailed results.")

if __name__ == '__main__':
    main()