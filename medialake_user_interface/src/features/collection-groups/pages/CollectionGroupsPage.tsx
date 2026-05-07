/**
 * Collection Groups Page
 * Main page for managing collection groups
 */

import React, { useState } from "react";
import { Box, Container } from "@mui/material";
import { CollectionGroupsList } from "../components/CollectionGroupsList";
import { CollectionGroupForm } from "../components/CollectionGroupForm";
import type { CollectionGroup } from "../types";

export const CollectionGroupsPage: React.FC = () => {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<CollectionGroup | null>(null);

  const handleCreateClick = () => {
    setSelectedGroup(null);
    setFormOpen(true);
  };

  const handleEditClick = (group: CollectionGroup) => {
    setSelectedGroup(group);
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setSelectedGroup(null);
  };

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        <CollectionGroupsList onCreateClick={handleCreateClick} onEditClick={handleEditClick} />

        <CollectionGroupForm open={formOpen} onClose={handleFormClose} group={selectedGroup} />
      </Box>
    </Container>
  );
};
