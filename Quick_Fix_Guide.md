# Quick Fix Guide for Map State ItemsPath Issue

## Immediate Fix for 12labs Pipeline

If you need an immediate fix for the 12labs pipeline without waiting for the full implementation, you can manually update the state machine definition:

1. Go to the AWS Step Functions console
2. Find the state machine for your 12labs pipeline
3. Click on "Edit"
4. In the state machine definition, find the Map state (Map___dndnode_27_)
5. Change the ItemsPath from "$.items" to "$.payload.externalTaskResults"
6. Save the changes

Example change:

```json
// Before
"Map___dndnode_27_": {
  "Type": "Map",
  "ItemsPath": "$.items",
  "MaxConcurrency": 0,
  "Iterator": {
    // ...
  },
  "Next": "Success___dndnode_28_"
}

// After
"Map___dndnode_27_": {
  "Type": "Map",
  "ItemsPath": "$.payload.externalTaskResults",
  "MaxConcurrency": 0,
  "Iterator": {
    // ...
  },
  "Next": "Success___dndnode_28_"
}
```

## Common ItemsPath Patterns

Here are some common patterns for ItemsPath in different scenarios:

| Integration | Operation | Input Structure | Recommended ItemsPath |
|-------------|-----------|-----------------|----------------------|
| Twelve Labs | getEmbeddingTaskResults | `{ "metadata": {...}, "payload": { "externalTaskResults": [...] } }` | `$.payload.externalTaskResults` |
| Generic | Array at root | `{ "items": [...] }` | `$.items` |
| Generic | Array in results | `{ "results": [...] }` | `$.results` |
| Generic | Array in data | `{ "data": [...] }` | `$.data` |

## Debugging Map State Issues

If you encounter similar issues with other pipelines, follow these steps to debug:

1. Check the error message to identify the input structure
2. Look for array fields in the input that should be iterated over
3. Update the ItemsPath to point to the correct array field
4. Test the updated state machine

## Temporary Workaround Using a Pass State

If you can't directly edit the state machine definition, you can add a Pass state before the Map state to transform the data:

```json
"Transform_For_Map": {
  "Type": "Pass",
  "Parameters": {
    "metadata.$": "$.metadata",
    "items.$": "$.payload.externalTaskResults"
  },
  "Next": "Map___dndnode_27_"
}
```

This Pass state transforms the data to have an "items" field at the top level, which the Map state can then use with its default ItemsPath of "$.items".

## Long-term Solution

For a more permanent solution, follow the implementation steps in the Implementation_Steps.md document to make the Map state's ItemsPath configuration more intelligent and adaptable to different input structures.