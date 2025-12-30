import React, { useMemo, useState, useEffect } from "react";
import { Box, Typography, Paper } from "@mui/material";
import { RichTreeView } from "@mui/x-tree-view/RichTreeView";
import { TreeViewBaseItem } from "@mui/x-tree-view/models";
import { useNavigate } from "react-router-dom";
import { useGetCollections, Collection } from "@/api/hooks/useCollections";

interface CollectionTreeViewProps {
  currentCollectionId?: string;
  onCollectionSelect?: (collectionId: string) => void;
}

interface TreeNode extends TreeViewBaseItem {
  id: string;
  label: string;
  children?: TreeNode[];
}

export const CollectionTreeView: React.FC<CollectionTreeViewProps> = ({
  currentCollectionId,
  onCollectionSelect,
}) => {
  const navigate = useNavigate();
  const [expandedItems, setExpandedItems] = useState<string[]>([]);

  // Get all collections (not just root)
  const { data: allCollectionsResponse, isLoading: isLoadingRoot } = useGetCollections();

  // Build tree structure recursively
  const buildTree = (collection: Collection, allCollections: Collection[]): TreeNode => {
    // Find children of this collection
    const children = allCollections.filter((c) => c.parentId === collection.id);

    const node: TreeNode = {
      id: collection.id,
      label: `${collection.name}${
        collection.childCollectionCount > 0 ? ` (${collection.childCollectionCount})` : ""
      }`,
    };

    // Recursively build children
    if (children.length > 0) {
      node.children = children.map((child) => buildTree(child, allCollections));
    }

    return node;
  };

  const treeData = useMemo(() => {
    if (!allCollectionsResponse?.data) return [];

    const allCollections = allCollectionsResponse.data;

    // Filter to only root collections (no parentId)
    const rootCollections = allCollections.filter((c: Collection) => !c.parentId);

    return rootCollections.map((root) => buildTree(root, allCollections));
  }, [allCollectionsResponse]);

  // Function to get all ancestor IDs for a given collection
  const getAncestorIds = (collectionId: string, allCollections: Collection[]): string[] => {
    const ancestors: string[] = [];
    let currentId = collectionId;

    while (currentId) {
      const collection = allCollections.find((c) => c.id === currentId);
      if (!collection || !collection.parentId) break;

      ancestors.push(collection.parentId);
      currentId = collection.parentId;
    }

    return ancestors;
  };

  // Auto-expand to the current collection when it changes
  useEffect(() => {
    if (currentCollectionId && allCollectionsResponse?.data) {
      const allCollections = allCollectionsResponse.data;
      const ancestorIds = getAncestorIds(currentCollectionId, allCollections);

      // Merge with existing expanded items to maintain user's manual expansions
      setExpandedItems((prev) => {
        const newExpanded = new Set([...prev, ...ancestorIds]);
        return Array.from(newExpanded);
      });
    }
  }, [currentCollectionId, allCollectionsResponse]);

  const handleItemClick = (event: React.SyntheticEvent, itemId: string) => {
    if (onCollectionSelect) {
      onCollectionSelect(itemId);
    } else {
      navigate(`/collections/${itemId}/view`);
    }
  };

  const handleExpandedItemsChange = (event: React.SyntheticEvent, itemIds: string[]) => {
    setExpandedItems(itemIds);
  };

  if (isLoadingRoot) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Loading collections...
        </Typography>
      </Box>
    );
  }

  if (!treeData || treeData.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No collections found
        </Typography>
      </Box>
    );
  }

  return (
    <Paper
      elevation={0}
      sx={{
        height: "100%",
        overflow: "auto",
        border: 1,
        borderColor: "divider",
      }}
    >
      <Box sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600, color: "text.secondary" }}>
          Collection Hierarchy
        </Typography>
        <RichTreeView
          items={treeData}
          selectedItems={currentCollectionId ? [currentCollectionId] : []}
          expandedItems={expandedItems}
          onExpandedItemsChange={handleExpandedItemsChange}
          onItemClick={handleItemClick}
          sx={{
            "& .MuiTreeItem-content": {
              py: 0.5,
              borderRadius: 1,
              "&:hover": {
                backgroundColor: "action.hover",
              },
              "&.Mui-selected": {
                backgroundColor: "primary.light",
                "&:hover": {
                  backgroundColor: "primary.light",
                },
              },
            },
          }}
        />
      </Box>
    </Paper>
  );
};
