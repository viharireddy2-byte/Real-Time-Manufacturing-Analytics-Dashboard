metadata name = 'Event Hub in Existing Namespace'
metadata description = '''Deploys an Event Hub in an existing namespace that may be in a different resource group or subscription.
This module exists because Bicep requires modules for cross-scope deployments (deploying to a different subscription/RG than the main deployment).

Usage Scenario:
- Main deployment to: subscription A, resource group "rg-rti-demo"
- Existing namespace in: subscription B, resource group "rg-corporate-eventhubs"
- Result: This module deploys to subscription B's resource group to create the Event Hub there
'''

// ============================================================================
// PARAMETERS
// ============================================================================

@description('The name of the existing Event Hub Namespace')
param namespaceName string

@description('The name of the Event Hub to create')
param eventHubName string

@description('The object ID of the user to grant Data Sender role')
param userObjectId string

@description('Message retention in days')
param messageRetentionInDays int = 1

// ============================================================================
// RESOURCES
// ============================================================================

// Reference the existing Event Hub Namespace
resource existingNamespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: namespaceName
}

// Create new Event Hub in the existing namespace
resource newEventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: existingNamespace
  name: eventHubName
  properties: {
    messageRetentionInDays: messageRetentionInDays
  }
}

// Grant Event Hub Data Sender role to the deploying user on the Event Hub resource. This allows the user to send messages to the Event Hub after deployment.
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(newEventHub.id, userObjectId, 'Azure Event Hubs Data Sender')
  scope: newEventHub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638d8f975') // Azure Event Hubs Data Sender
    principalId: userObjectId
    principalType: 'User'
  }
}

// ============================================================================
// OUTPUTS
// ============================================================================

@description('The resource ID of the created Event Hub')
output eventHubId string = newEventHub.id

@description('The name of the created Event Hub')
output eventHubName string = newEventHub.name

@description('The resource ID of the namespace')
output namespaceId string = existingNamespace.id
