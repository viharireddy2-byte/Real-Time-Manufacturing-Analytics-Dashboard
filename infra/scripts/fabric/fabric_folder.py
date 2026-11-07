#!/usr/bin/env python3
"""
Fabric Folder Management Module

This module provides folder management functionality for Microsoft Fabric operations.
It creates folders in the workspace if they don't exist, or returns existing folder information.

Usage:
    python fabric_folder.py --workspace-id "workspace-guid" --folder-name "MyFolder"
    python fabric_folder.py --workspace-id "workspace-guid" --folder-name "MyFolder" --parent-folder-id "parent-guid"

Requirements:
    - fabric_api.py module in the same directory
    - Azure CLI authentication or other Azure credentials configured
    - Appropriate permissions to create/read folders in the workspace
"""

import argparse
import sys
from typing import Optional, Dict, Any
from fabric_api import FabricWorkspaceApiClient, FabricApiError


def setup_folder(workspace_client: FabricWorkspaceApiClient, 
                folder_name: str,
                parent_folder_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a folder if it doesn't exist, or return existing folder information.
    
    Args:
        workspace_client: Authenticated FabricWorkspaceApiClient instance
        folder_name: Name of the folder to create or find
        parent_folder_id: Optional parent folder ID (None for root folder)
        
    Returns:
        dict: Folder information containing id, displayName, etc.
        
    Raises:
        FabricApiError: If folder operations fail
    """
    print(f"📁 Setting up folder: '{folder_name}'")
    
    try:
        # Check if folder already exists
        existing_folder = workspace_client.get_folder_by_name(folder_name, parent_folder_id)
        
        if existing_folder:
            folder_id = existing_folder['id']
            print(f"ℹ️  Using existing folder: '{folder_name}' ({folder_id})")
            return existing_folder
        else:
            # Create the folder if it doesn't exist
            if parent_folder_id:
                print(f"📁 Creating new folder: '{folder_name}' under parent {parent_folder_id}")
            else:
                print(f"📁 Creating new folder: '{folder_name}' in workspace root")
            
            folder_id = workspace_client.create_folder(folder_name, parent_folder_id)
            
            # Get the created folder information
            folders = workspace_client.get_folders()
            created_folder = next((f for f in folders if f['id'] == folder_id), None)
            
            if not created_folder:
                raise FabricApiError(f"Failed to retrieve created folder information for '{folder_name}'")
            
            print(f"✅ Successfully created folder: '{folder_name}' ({folder_id})")
            return created_folder
            
    except FabricApiError as e:
        print(f"❌ Failed to setup folder '{folder_name}': {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error setting up folder '{folder_name}': {e}")
        raise FabricApiError(f"Error setting up folder: {e}")


def main():
    """Main function to handle command line arguments and execute folder setup."""
    parser = argparse.ArgumentParser(
        description='Create or find a folder in Microsoft Fabric workspace',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create/find root folder
  python fabric_folder.py --workspace-id "12345678-1234-1234-1234-123456789abc" --folder-name "DataProcessing"
  
  # Create/find subfolder
  python fabric_folder.py --workspace-id "12345678-1234-1234-1234-123456789abc" --folder-name "Analysis" --parent-folder-id "87654321-4321-4321-4321-210987654321"
        '''
    )
    
    parser.add_argument('--workspace-id', 
                      required=True,
                      help='Workspace ID (GUID) where the folder will be created or found')
    
    parser.add_argument('--folder-name',
                      required=True, 
                      help='Name of the folder to create or find')
    
    parser.add_argument('--parent-folder-id',
                      help='Optional parent folder ID (for creating subfolders)')
    
    args = parser.parse_args()
    
    try:
        # Initialize Fabric API client for the workspace
        workspace_client = FabricWorkspaceApiClient(workspace_id=args.workspace_id)
        
        # Setup the folder
        folder_info = setup_folder(
            workspace_client=workspace_client,
            folder_name=args.folder_name,
            parent_folder_id=args.parent_folder_id
        )
        
        # Print summary
        print("\n" + "="*50)
        print("📋 FOLDER SETUP SUMMARY")
        print("="*50)
        print(f"Folder Name: {folder_info.get('displayName', 'N/A')}")
        print(f"Folder ID: {folder_info.get('id', 'N/A')}")
        print(f"Workspace ID: {args.workspace_id}")
        if args.parent_folder_id:
            print(f"Parent Folder ID: {args.parent_folder_id}")
        else:
            print(f"Location: Workspace root")
        print("="*50)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())