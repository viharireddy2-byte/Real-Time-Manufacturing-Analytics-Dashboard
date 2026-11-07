#!/usr/bin/env python3
"""
Fabric Data Agent Setup Module

This module provides Data Agent creation functionality for Microsoft Fabric operations.
It creates a new Data Agent in the specified workspace, configures it with AI instructions,
and creates/runs a configuration notebook.

Usage:
    python fabric_data_agent.py --workspace-id "workspace-guid" --data-agent-name "MyDataAgent" --kusto-db-id "kusto-db-id" --kusto-db-workspace-id "kusto-db-workspace-id"

Requirements:
    - fabric_api.py module in the same directory
    - Azure CLI authentication or other Azure credentials configured
    - Appropriate permissions to create Data Agents and notebooks in the workspace
"""

import argparse
import sys
import os
import json
import base64
from typing import Optional
from fabric_api import FabricWorkspaceApiClient, FabricApiError


def read_file_content(file_path: str) -> str:
    """
    Read content from a file.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        File content as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If file can't be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {e}")


def replace_tokens_in_content(content: str, tokens: dict) -> str:
    """
    Replace tokens in content with their values, properly escaping for JSON.
    
    Args:
        content: Content with tokens to replace
        tokens: Dictionary mapping token names to replacement values
        
    Returns:
        Content with tokens replaced and properly escaped
    """
    for token, value in tokens.items():
        # Escape the value for JSON if it's a string
        if isinstance(value, str):
            # Escape backslashes, quotes, and control characters
            escaped_value = json.dumps(value)[1:-1]  # Remove surrounding quotes from json.dumps
        else:
            escaped_value = str(value)
        content = content.replace(token, escaped_value)
    return content


def setup_data_agent(workspace_client: FabricWorkspaceApiClient, 
                                   data_agent_name: str,
                                   kusto_db_id: str,
                                   kusto_db_workspace_id: str,
                                   environment_id: str,
                                   notebook_name: str,
                                   notebook_folder_id: Optional[str] = None,
                                   data_agent_folder_id: Optional[str] = None) -> dict:
    """
    Create a Data Agent and configure it with a notebook.
    
    Args:
        workspace_client: Authenticated FabricWorkspaceApiClient instance
        data_agent_name: Name of the Data Agent to create
        kusto_db_id: ID of the Kusto database to connect as data source
        kusto_db_workspace_id: ID of the workspace containing the Kusto database
        environment_id: ID of the environment for data agent configuration
        notebook_name: Name of the configuration notebook to create
        notebook_folder_id: Optional folder ID where to create the notebook
        data_agent_folder_id: Optional folder ID where to create the data agent
        
    Returns:
        dict: Data Agent information if successful
        
    Raises:
        FabricApiError: If creation fails
    """
    print(f"🤖 Creating Data Agent: '{data_agent_name}'")
    
    try:
        # Check if Data Agent already exists
        existing_agent = workspace_client.get_data_agent_by_name(data_agent_name)
        if existing_agent:
            data_agent = existing_agent
            print(f"ℹ️  Data Agent '{data_agent_name}' already exists")
        else:
            # Create the Data Agent
            data_agent = workspace_client.create_data_agent(data_agent_name, folder_id=data_agent_folder_id)
            print(f"✅ Successfully created Data Agent: {data_agent_name}")
        
        # Get data agent ID and fail if not found
        data_agent_id = data_agent.get('id')
        if not data_agent_id:
            raise FabricApiError(f"Failed to retrieve Data Agent ID for '{data_agent_name}'")
        
        # Calculate repository directory (script is in infra/scripts/fabric/, so go up 3 levels)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        
        # Read configuration files
        print(f"📖 Reading configuration files from: {repo_dir}")
        
        # Paths to configuration files
        notebook_path = os.path.join(repo_dir, "src", "notebooks", "configure_data_agent.ipynb")
        agent_instructions_path = os.path.join(repo_dir, "src", "data_agent", "agent_instructions.md")
        data_source_description_path = os.path.join(repo_dir, "src", "data_agent", "data_source_description.md")
        data_source_instructions_path = os.path.join(repo_dir, "src", "data_agent", "data_source_instructions.md")
        query_examples_path = os.path.join(repo_dir, "src", "data_agent", "query_examples.json")
        
        # Read all configuration files
        notebook_content = read_file_content(notebook_path)
        agent_instructions = read_file_content(agent_instructions_path)
        data_source_description = read_file_content(data_source_description_path)
        data_source_instructions = read_file_content(data_source_instructions_path)
        query_examples_json = read_file_content(query_examples_path)
        
        print(f"✅ Successfully read all configuration files")
        
        # Parse query examples JSON to Python dict format for replacement
        query_examples_dict = json.loads(query_examples_json)
        query_examples_python = str(query_examples_dict)
        
        # Replace tokens in notebook content
        print(f"🔄 Replacing configuration tokens...")
        tokens = {
            "__AGENT_ID__": data_agent_id,
            "__KQL_DATABASE_ID__": kusto_db_id,
            "__KQL_DATABASE_WORKSPACE_ID__": kusto_db_workspace_id,
            "__ENVIRONMENT_ID__": environment_id,
            "__WORKSPACE_ID__": workspace_client.workspace_id,
            "__AGENT_INSTRUCTIONS__": agent_instructions,
            "__DATA_SOURCE_INSTRUCTIONS__": data_source_instructions,
            "__DATA_SOURCE_DESCRIPTION__": data_source_description,
            "__QUERY_EXAMPLES__": query_examples_python
        }
        
        configured_notebook_content = replace_tokens_in_content(notebook_content, tokens)
        print(f"✅ Successfully replaced configuration tokens")
        
        # Create or update notebook
        print(f"📓 Creating/updating notebook: '{notebook_name}'")
        
        # Check if notebook already exists
        notebook = workspace_client.get_notebook_by_name(notebook_name)
        
        # Parse and encode notebook content as base64
        notebook_json = json.loads(configured_notebook_content)
        notebook_base64 = base64.b64encode(
            json.dumps(notebook_json).encode('utf-8')
        ).decode('utf-8')
        
        if notebook:
            # Update existing notebook
            notebook_id = notebook.get('id')
            if not notebook_id:
                raise FabricApiError(f"Failed to retrieve notebook ID for existing notebook '{notebook_name}'")
            print(f"ℹ️  Notebook '{notebook_name}' already exists, updating...")
            workspace_client.update_notebook(notebook_id, notebook_name, notebook_base64, notebook_folder_id)
            print(f"✅ Successfully updated notebook: {notebook_name} ({notebook_id})")
        else:
            # Create new notebook
            notebook = workspace_client.create_notebook(notebook_name, notebook_base64, notebook_folder_id)
            notebook_id = notebook.get('id')
            if not notebook_id:
                raise FabricApiError(f"Failed to retrieve notebook ID for created notebook '{notebook_name}'")
            print(f"✅ Successfully created notebook: {notebook_name} ({notebook_id})")
        
        # Run the notebook
        print(f"▶️  Running configuration notebook...")
        job_result = workspace_client.schedule_notebook_job(notebook_id)
        
        print(f"📊 Notebook execution completed:")
        print(f"   Status: {job_result.get('status')}")
        print(f"   Duration: {job_result.get('duration')}")
        
        if job_result.get('status') != 'Completed':
            if 'error' in job_result:
                print(f"   Error: {job_result.get('error')}")
            raise FabricApiError(f"Notebook execution failed with status: {job_result.get('status')}")
        
        print(f"✅ Data Agent configuration completed successfully!")
        
        return data_agent
        
    except FabricApiError as e:
        print(f"❌ Failed to create/configure Data Agent '{data_agent_name}': {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error creating/configuring Data Agent '{data_agent_name}': {e}")
        raise FabricApiError(f"Error creating Data Agent: {e}")


def main():
    """Main function to create a Data Agent and configure it via notebook."""
    parser = argparse.ArgumentParser(
        description="Create a Microsoft Fabric Data Agent and configure it with AI instructions via notebook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create and configure Data Agent with default notebook name
  python fabric_data_agent.py --workspace-id "12345678-1234-1234-1234-123456789012" --data-agent-name "Operations Agent" --kusto-db-id "87654321-4321-4321-4321-210987654321" --kusto-db-workspace-id "87654321-4321-4321-4321-210987654321" --environment-id "99999999-8888-7777-6666-555544443333"
  
  # Create and configure Data Agent with custom notebook name
  python fabric_data_agent.py --workspace-id "12345678-1234-1234-1234-123456789012" --data-agent-name "Operations Agent" --kusto-db-id "87654321-4321-4321-4321-210987654321" --kusto-db-workspace-id "87654321-4321-4321-4321-210987654321" --environment-id "99999999-8888-7777-6666-555544443333" --notebook-name "My Custom Agent Config"
        """
    )
    
    parser.add_argument(
        "--workspace-id", 
        required=True, 
        help="ID of the workspace where the Data Agent will be created"
    )
    
    parser.add_argument(
        "--data-agent-name", 
        required=True, 
        help="Name of the Data Agent to create"
    )
    
    parser.add_argument(
        "--kusto-db-id", 
        required=True, 
        help="ID of the Kusto database to add as a data source"
    )
    
    parser.add_argument(
        "--kusto-db-workspace-id", 
        required=True, 
        help="ID of the workspace containing the Kusto database"
    )
    
    parser.add_argument(
        "--environment-id", 
        required=True, 
        help="ID of the environment for data agent configuration"
    )
    
    parser.add_argument(
        "--notebook-name", 
        required=False,
        default=None,
        help="Name of the configuration notebook (default: 'Configure Data Agent - <data-agent-name>')"
    )
    
    parser.add_argument(
        "--notebook-folder-id", 
        required=False,
        help="Optional folder ID where to create the notebook"
    )
    
    parser.add_argument(
        "--data-agent-folder-id", 
        required=False,
        help="Optional folder ID where to create the data agent"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set default notebook name if not provided
    notebook_name = args.notebook_name or f"Configure Data Agent - {args.data_agent_name}"
    
    # Create workspace client
    try:
        workspace_client = FabricWorkspaceApiClient(workspace_id=args.workspace_id)
        
        # Create the Data Agent and configure it
        result = setup_data_agent(
            workspace_client=workspace_client,
            data_agent_name=args.data_agent_name,
            kusto_db_id=args.kusto_db_id,
            kusto_db_workspace_id=args.kusto_db_workspace_id,
            environment_id=args.environment_id,
            notebook_name=notebook_name,
            notebook_folder_id=args.notebook_folder_id,
            data_agent_folder_id=args.data_agent_folder_id
        )
        
        print(f"\n🎉 Final Results:")
        print(f"   Data Agent ID: {result.get('id', 'N/A')}")
        print(f"   Data Agent Name: {args.data_agent_name}")
        print(f"   KQL Database ID: {args.kusto_db_id}")
        print(f"   Configuration Status: Complete")
        print(f"   Ready for use in Microsoft Fabric!")
        
    except FabricApiError as e:
        print(f"❌ Fabric API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()