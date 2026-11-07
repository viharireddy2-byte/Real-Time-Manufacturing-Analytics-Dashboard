#!/usr/bin/env python3
"""
Fabric Workspace Creation and Capacity Assignment Module

This module provides workspace creation and capacity assignment functionality for Microsoft Fabric operations.
It creates a new Microsoft Fabric workspace (if it doesn't exist) and assigns it 
to a specified capacity.

Usage:
    python fabric_workspace.py --capacity-name "MyCapacity" [--workspace-name "MyWorkspace"]

Requirements:
    - fabric_api.py module in the same directory
    - Azure CLI authentication or other Azure credentials configured
    - Appropriate permissions to create workspaces and assign capacities
"""

import argparse
from fabric_api import FabricApiClient, FabricWorkspaceApiClient, FabricApiError

def setup_workspace(fabric_client: FabricApiClient, capacity_name: str, workspace_name: str) -> str:
    """
    Create a workspace (if it doesn't exist) and assign it to the specified capacity.
    
    Args:
        fabric_client: Authenticated FabricApiClient instance
        capacity_name: Name of the capacity to assign the workspace to
        workspace_name: Name of the workspace to create
        
    Returns:
        str: Workspace ID if successful, or None if failed
    """
    # Step 1: Get or create workspace
    existing_workspace = fabric_client.get_workspace(workspace_name)
    
    if existing_workspace:
        workspace_id = existing_workspace['id']
        print(f"ℹ️  Using existing workspace: {workspace_name} ({workspace_id})")
    else:
        print(f"📁 Creating new workspace: '{workspace_name}'")
        try:
            workspace_id = fabric_client.create_workspace(name=workspace_name)
            print(f"✅ Successfully created workspace: {workspace_name} ({workspace_id})")
        except FabricApiError as e:
            if e.status_code == 409:
                # Handle race condition where workspace was created between check and create
                print(f"ℹ️ Workspace '{workspace_name}' already exists (created during operation)")
                existing_workspace = fabric_client.get_workspace(workspace_name)
                workspace_id = existing_workspace['id']
            else:
                print(f"❌ Failed to create workspace: {e}")
                raise

    # Step 2: Find the capacity
    print(f"🔍 Searching for capacity: '{capacity_name}'")
    capacity = fabric_client.get_capacity(capacity_name)
    if not capacity:
        print(f"❌ Capacity '{capacity_name}' not found.")
        return None

    capacity_id = capacity['id']
    print(f"✅ Capacity found: {capacity['displayName']} ({capacity_id})")

    # Step 3: Assign workspace to capacity
    print(f"⚡ Assigning workspace to capacity '{capacity_name}'...")
    workspace_client = FabricWorkspaceApiClient(workspace_id=workspace_id)
    workspace_client.assign_to_capacity(capacity_id)
    print(f"✅ Successfully assigned workspace to capacity")
    
    return workspace_id

def main():
    """Main function to handle command line arguments and execute workspace setup."""
    parser = argparse.ArgumentParser(
        description="Create a Fabric workspace and assign it to a capacity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fabric_workspace.py --capacity-name "Dev Capacity" --workspace-name "Development Workspace"
        """
    )
    
    parser.add_argument(
        "--capacity-name", 
        required=True, 
        help="Name of the capacity to assign the workspace to"
    )
    
    parser.add_argument(
        "--workspace-name", 
        required=True, 
        help="Name of the workspace to create"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute the main logic
    fabric_client = FabricApiClient()
    
    result = setup_workspace(
        fabric_client=fabric_client,
        capacity_name=args.capacity_name,
        workspace_name=args.workspace_name
    )
    
    print(f"\n✅ Workspace ID: {result if result else 'Failed'}")
    print(f"✅ Workspace Name: {args.workspace_name}")


if __name__ == "__main__":
    main()
