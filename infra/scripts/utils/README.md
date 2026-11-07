# Utility Scripts

This folder contains utility scripts for managing Microsoft Fabric resources and automating common tasks in the Real-Time Intelligence Operations solution.

## Table of Contents

- [Utility Scripts](#utility-scripts)
  - [Table of Contents](#table-of-contents)
  - [Get-FabricActivatorDefinition.ps1](#get-fabricactivatordefinitionps1)
  - [Get-FabricEventstreamDefinition.ps1](#get-fabriceventstreamdefinitionps1)
  - [Get-FabricRealTimeDashboardDefinition.ps1](#get-fabricrealtimedashboarddefinitionps1)
  - [Run-FabricJsonTokenizer.ps1](#run-fabricjsontokenizerps1)
  - [Run-PythonScript.ps1](#run-pythonscriptps1)

## Get-FabricActivatorDefinition.ps1
Retrieves and decodes Microsoft Fabric Activator (Reflex) definitions using the Fabric REST API.

**Purpose:** Download activator configurations including entities and triggers for backup or deployment purposes.

**Required Parameters:**
- `-WorkspaceId`: GUID of the Fabric workspace containing the activator
- `-ReflexId`: GUID of the activator (reflex) to retrieve

**Optional Parameters:**
- `-FolderPath`: Path to save decoded definition files (default: `src/activator` relative to repository root)
- `-Format`: Format parameter for the activator definition (as supported by the API)
- `-SkipTokenization`: Skip automatic tokenization of JSON files after creation (default: tokenization is performed)

**Default Behavior:** Saves files to `src/activator` folder and automatically tokenizes the resulting JSON files.

**Examples:**
```powershell
# Basic usage with default folder and tokenization
.\Get-FabricActivatorDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -ReflexId "bbbbcccc-1111-dddd-2222-eeee3333ffff"

# Custom folder path
.\Get-FabricActivatorDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -ReflexId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -FolderPath "C:\temp\activator"

# Skip tokenization
.\Get-FabricActivatorDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -ReflexId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -SkipTokenization
```

## Get-FabricEventstreamDefinition.ps1
Retrieves and decodes Microsoft Fabric Eventstream definitions using the Fabric REST API.

**Purpose:** Download eventstream configurations including sources, destinations, and operators.

**Required Parameters:**
- `-WorkspaceId`: GUID of the Fabric workspace containing the eventstream
- `-EventstreamId`: GUID of the eventstream to retrieve

**Optional Parameters:**
- `-FolderPath`: Path to save decoded definition files (default: `src/eventstream` relative to repository root)
- `-Format`: Format parameter for the eventstream definition (as supported by the API)
- `-SkipTokenization`: Skip automatic tokenization of JSON files after creation (default: tokenization is performed)

**Default Behavior:** Saves files to `src/eventstream` folder and automatically tokenizes the resulting JSON files.

**Examples:**
```powershell
# Basic usage with default folder and tokenization
.\Get-FabricEventstreamDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -EventstreamId "bbbbcccc-1111-dddd-2222-eeee3333ffff"

# Custom folder path
.\Get-FabricEventstreamDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -EventstreamId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -FolderPath "C:\temp\eventstream"

# Skip tokenization
.\Get-FabricEventstreamDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -EventstreamId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -SkipTokenization
```

## Get-FabricRealTimeDashboardDefinition.ps1
Retrieves and decodes Microsoft Fabric Real-Time Dashboard (KQL Dashboard) definitions using the Fabric REST API.

**Purpose:** Download dashboard configurations including queries, parameters, and visualization tiles.

**Required Parameters:**
- `-WorkspaceId`: GUID of the Fabric workspace containing the KQL dashboard
- `-KqlDashboardId`: GUID of the KQL dashboard to retrieve

**Optional Parameters:**
- `-FolderPath`: Path to save decoded definition files (default: `src/realTimeDashboard` relative to repository root)
- `-Format`: Format parameter for the KQL dashboard definition (as supported by the API)
- `-SkipTokenization`: Skip automatic tokenization of JSON files after creation (default: tokenization is performed)

**Default Behavior:** Saves files to `src/realTimeDashboard` folder and automatically tokenizes the resulting JSON files.

**Examples:**
```powershell
# Basic usage with default folder and tokenization
.\Get-FabricRealTimeDashboardDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -KqlDashboardId "bbbbcccc-1111-dddd-2222-eeee3333ffff"

# Custom folder path
.\Get-FabricRealTimeDashboardDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -KqlDashboardId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -FolderPath "C:\temp\dashboard"

# Skip tokenization
.\Get-FabricRealTimeDashboardDefinition.ps1 -WorkspaceId "aaaabbbb-0000-cccc-1111-dddd2222eeee" -KqlDashboardId "bbbbcccc-1111-dddd-2222-eeee3333ffff" -SkipTokenization
```

## Run-FabricJsonTokenizer.ps1
Processes JSON configuration files and replaces specific values with standardized tokens for deployment automation.

**Purpose:** Tokenize Fabric resource definitions to make them reusable across different environments.

**Required Parameters:**
- `-SchemaType`: The schema type to process (valid values: `Activator`, `Eventstream`, `RealTimeDashboard`)

**Optional Parameters:**
- `-JsonFilePath`: Path to the JSON file to tokenize (default: calculated based on SchemaType)
- `-OutputPath`: Output path for the tokenized JSON (default: overwrites the original file)
- `-DryRun`: Shows what would be changed without modifying files (default: false)
- `-SaveTokenMap`: Creates a separate token mapping file alongside the tokenized JSON (default: false)

**Default Behavior:** 
- Activator: Processes `ReflexEntities.json` from `src/activator/`
- Eventstream: Processes `eventstream.json` from `src/eventstream/`
- RealTimeDashboard: Processes `RealTimeDashboard.json` from `src/realTimeDashboard/`

**Examples:**
```powershell
# Basic usage - tokenize eventstream with default settings
.\Run-FabricJsonTokenizer.ps1 -SchemaType Eventstream

# Dry run to preview changes
.\Run-FabricJsonTokenizer.ps1 -SchemaType Activator -DryRun

# Save token mapping file
.\Run-FabricJsonTokenizer.ps1 -SchemaType RealTimeDashboard -SaveTokenMap

# Custom output path
.\Run-FabricJsonTokenizer.ps1 -SchemaType Activator -OutputPath "ReflexEntities_tokenized.json"

# Custom input file
.\Run-FabricJsonTokenizer.ps1 -SchemaType Eventstream -JsonFilePath "C:\custom\eventstream.json"
```

## Run-PythonScript.ps1
Unified script to execute Python scripts with proper environment management.

**Purpose:** Execute Python scripts with automatic virtual environment setup and dependency management.

**Required Parameters:**
- `-ScriptPath`: Relative path to the Python script to execute (relative to repository root)

**Optional Parameters:**
- `-ScriptArguments`: Array of arguments to pass to the Python script (default: empty array)
- `-SkipPythonVirtualEnvironment`: Use system Python directly instead of creating virtual environment (default: false)
- `-SkipPythonDependencies`: Skip installing Python dependencies (default: false, assumes pre-installed)
- `-SkipPipUpgrade`: Skip upgrading pip to latest version (default: false)
- `-RequirementsPath`: Path to requirements.txt file (default: repository root `requirements.txt`)

**Default Behavior:** Creates a virtual environment, upgrades pip, installs dependencies from `requirements.txt`, then executes the specified Python script.

**Examples:**
```powershell
# Basic usage with full environment setup
.\Run-PythonScript.ps1 -ScriptPath "infra/scripts/fabric/deploy_fabric_rti.py"

# Skip virtual environment and use system Python
.\Run-PythonScript.ps1 -ScriptPath "infra/scripts/fabric/deploy_fabric_rti.py" -SkipPythonVirtualEnvironment

# Skip dependency installation (assume pre-installed)
.\Run-PythonScript.ps1 -ScriptPath "infra/scripts/fabric/delete_fabric_rti.py" -SkipPythonDependencies

# Pass arguments to the Python script
.\Run-PythonScript.ps1 -ScriptPath "infra/scripts/fabric/deploy_fabric_rti.py" -ScriptArguments @("--verbose", "--config", "config.json")

# Use custom requirements file
.\Run-PythonScript.ps1 -ScriptPath "src/sample_data.py" -RequirementsPath "src/requirements_basics.txt"
```