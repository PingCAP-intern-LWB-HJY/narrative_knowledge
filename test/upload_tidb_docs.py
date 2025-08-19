#!/usr/bin/env python3
"""
Script to generate curl commands for uploading TiDB documentation files
based on content analysis and topic determination.
"""

import os
import json
import subprocess
from pathlib import Path

class TiDBDocsUploader:
    def __init__(self, docs_path="/Users/hjy/Downloads/docs-master"):
        self.docs_path = Path(docs_path)
        self.base_url = "https://github.com/pingcap/docs/blob/master"
        
    def get_tidb_cloud_files(self):
        """Get relevant TiDB Cloud documentation files"""
        tidb_cloud_files = [
            # Core TiDB Cloud files
            ("tidb-cloud/tidb-cloud-intro.md", "TiDB Cloud Introduction"),
            ("tidb-cloud/tidb-cloud-quickstart.md", "TiDB Cloud Quickstart"),
            ("tidb-cloud/tidb-cloud-htap-quickstart.md", "TiDB Cloud HTAP Quickstart"),
            ("tidb-cloud/get-started-with-cli.md", "TiDB Cloud CLI"),
            ("tidb-cloud/tidb-cloud-poc.md", "TiDB Cloud PoC"),
            ("tidb-cloud/key-concepts.md", "TiDB Cloud Key Concepts"),
            ("tidb-cloud/architecture-concepts.md", "TiDB Cloud Architecture"),
            ("tidb-cloud/database-schema-concepts.md", "TiDB Cloud Database Schema"),
            ("tidb-cloud/transaction-concepts.md", "TiDB Cloud Transactions"),
            ("tidb-cloud/sql-concepts.md", "TiDB Cloud SQL"),
            ("tidb-cloud/ai-feature-concepts.md", "TiDB Cloud AI Features"),
            ("tidb-cloud/data-service-concepts.md", "TiDB Cloud Data Service"),
            ("tidb-cloud/scalability-concepts.md", "TiDB Cloud Scalability"),
            ("tidb-cloud/serverless-high-availability.md", "TiDB Cloud Serverless HA"),
            ("tidb-cloud/high-availability-with-multi-az.md", "TiDB Cloud Dedicated HA"),
            ("tidb-cloud/monitoring-concepts.md", "TiDB Cloud Monitoring"),
            ("tidb-cloud/data-streaming-concepts.md", "TiDB Cloud Data Streaming"),
            ("tidb-cloud/backup-and-restore-concepts.md", "TiDB Cloud Backup & Restore"),
            ("tidb-cloud/security-concepts.md", "TiDB Cloud Security"),
            
            # Development guides
            ("develop/dev-guide-overview.md", "Developer Guide Overview"),
            ("develop/dev-guide-build-cluster-in-cloud.md", "Build TiDB Cloud Cluster"),
            ("develop/dev-guide-tidb-crud-sql.md", "TiDB CRUD SQL"),
            ("develop/dev-guide-choose-driver-or-orm.md", "Choose Driver or ORM"),
            ("develop/dev-guide-schema-design-overview.md", "Schema Design Overview"),
            ("develop/dev-guide-create-database.md", "Create Database"),
            ("develop/dev-guide-create-table.md", "Create Table"),
            ("develop/dev-guide-create-secondary-indexes.md", "Create Secondary Indexes"),
            
            # Vector search
            ("vector-search/vector-search-overview.md", "Vector Search Overview"),
            ("vector-search/vector-search-get-started-using-sql.md", "Vector Search SQL"),
            ("vector-search/vector-search-get-started-using-python.md", "Vector Search Python"),
            
            # Migration
            ("tidb-cloud/tidb-cloud-migration-overview.md", "TiDB Cloud Migration Overview"),
            ("tidb-cloud/create-tidb-cluster-serverless.md", "Create Serverless Cluster"),
            ("tidb-cloud/create-tidb-cluster.md", "Create Dedicated Cluster"),
        ]
        
        # Filter files that exist
        existing_files = []
        for file_path, description in tidb_cloud_files:
            full_path = self.docs_path / file_path
            if full_path.exists():
                existing_files.append((file_path, description))
        
        return existing_files
    
    def generate_curl_commands(self, files_batch, batch_name):
        """Generate curl commands for batch upload using DOCS_PATH parameter"""
        curl_parts = ["curl -X POST \"http://localhost:8000/api/v1/save\" \\"]
        
        # Add files using DOCS_PATH variable
        for file_path, _ in files_batch:
            curl_parts.append(f"  -F \"files=@$DOCS_PATH/{file_path}\" \\")
        
        # Add links
        links = [f"{self.base_url}/{file_path}" for file_path, _ in files_batch]
        links_json = json.dumps(links)
        curl_parts.append(f"  -F 'links={links_json}' \\")
        
        # Add metadata
        metadata = {
            "topic_name": f"tidb_cloud_{batch_name}",
            "force_regenerate": "False"
        }
        curl_parts.append(f"  -F 'metadata={json.dumps(metadata)}' \\")
        
        # Add target_type
        curl_parts.append("  -F \"target_type=knowledge_graph\"")
        
        return "\n".join(curl_parts)
    
    def create_upload_script(self):
        """Create the upload script with base path parameter"""
        files = self.get_tidb_cloud_files()
        
        if not files:
            print("No TiDB Cloud documentation files found!")
            return
        
        script_content = "#!/bin/bash\n"
        script_content += "# TiDB Cloud Documentation Upload Script\n"
        script_content += "# Generated automatically based on content analysis\n\n"
        script_content += "# Set the base path for documentation files\n"
        script_content += 'DOCS_PATH="${1:-/Users/hjy/Downloads/docs-master}"\n\n'
        script_content += "echo \"Using documentation path: $DOCS_PATH\"\n\n"
        
        # Split into logical batches
        batch1 = files[:8]  # Core concepts
        batch2 = files[8:16]  # Development guides
        batch3 = files[16:]  # Advanced features
        
        batches = [
            (batch1, "core_concepts"),
            (batch2, "development_guides"),
            (batch3, "advanced_features")
        ]
        
        for i, (batch, batch_name) in enumerate(batches, 1):
            if batch:  # Only add non-empty batches
                script_content += f"\n# Batch {i}: {batch_name.replace('_', ' ').title()}\n"
                script_content += self.generate_curl_commands(batch, batch_name)
                script_content += "\n\n"
        
        # Also create a single command for all files
        if len(files) <= 20:  # If total files <= 20, create single batch
            script_content += "\n# Single batch upload (all files)\n"
            script_content += self.generate_curl_commands(files, "complete_docs")
            script_content += "\n\n"
        
        # Create individual file upload commands
        script_content += "\n# Individual file uploads (for testing)\n"
        for file_path, description in files[:5]:  # First 5 for individual testing
            curl_cmd = self.generate_curl_commands([(file_path, description)], "single_file")
            script_content += f"\n# {description}\n"
            script_content += curl_cmd
            script_content += "\n\n"
        
        script_content += "\n# Usage:\n"
        script_content += "# ./upload_tidb_docs.sh [docs_path]\n"
        script_content += "# Example: ./upload_tidb_docs.sh /custom/path/to/docs\n"
        
        return script_content
    
    def create_file_list(self):
        """Create a list of files for reference"""
        files = self.get_tidb_cloud_files()
        
        list_content = "# TiDB Cloud Documentation Files\n\n"
        list_content += f"Total files to upload: {len(files)}\n\n"
        
        for i, (file_path, description) in enumerate(files, 1):
            full_path = self.docs_path / file_path
            github_url = f"{self.base_url}/{file_path}"
            list_content += f"{i}. {description}\n"
            list_content += f"   Local: {full_path}\n"
            list_content += f"   GitHub: {github_url}\n\n"
        
        return list_content

if __name__ == "__main__":
    uploader = TiDBDocsUploader()
    
    # Generate upload script
    script_content = uploader.create_upload_script()
    
    # Generate file list
    file_list = uploader.create_file_list()
    
    # Save files
    with open("upload_tidb_docs.sh", "w") as f:
        f.write(script_content)
    
    with open("tidb_docs_file_list.txt", "w") as f:
        f.write(file_list)
    
    # Make script executable
    os.chmod("upload_tidb_docs.sh", 0o755)
    
    print("Generated upload files:")
    print("1. upload_tidb_docs.sh - Main upload script")
    print("2. tidb_docs_file_list.txt - File reference list")
    print("\nTo run the upload:")
    print("  ./upload_tidb_docs.sh")
    print("\nOr use individual curl commands from the script")