import React from "react";
import {
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import { Extension as IntegrationIcon } from "@mui/icons-material";
import { IntegrationListItemProps } from "../types";

export const IntegrationListItem: React.FC<IntegrationListItemProps> = ({
  node,
  selected,
  onSelect,
}) => {
  const handleClick = React.useCallback(() => {
    onSelect(node);
  }, [node, onSelect]);

  return (
    <ListItem disablePadding>
      <ListItemButton
        selected={selected}
        onClick={handleClick}
        sx={{
          py: 2,
          "&:hover": {
            backgroundColor: "action.hover",
          },
          "&.Mui-selected": {
            backgroundColor: "transparent",
            borderLeft: 4,
            borderLeftColor: "primary.main",
            pl: "12px", // Compensate for border
            "&:hover": {
              backgroundColor: "action.hover",
            },
          },
          "& .MuiListItemIcon-root": {
            minWidth: 40,
          },
          "& .MuiListItemText-primary": {
            fontWeight: selected ? 600 : 400,
            color: selected ? "primary.main" : "text.primary",
          },
          "& .MuiListItemText-secondary": {
            color: "text.secondary",
            whiteSpace: "normal",
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
          },
        }}
      >
        <ListItemIcon>
          <IntegrationIcon color="primary" />
        </ListItemIcon>
        <ListItemText
          primary={node.info.title}
          secondary={node.info.description}
          primaryTypographyProps={{
            variant: "subtitle1",
            fontWeight: selected ? 600 : 500,
            color: selected ? "primary.main" : "text.primary",
          }}
          secondaryTypographyProps={{
            variant: "body2",
            color: "text.secondary",
          }}
        />
      </ListItemButton>
    </ListItem>
  );
};

export default React.memo(IntegrationListItem);
