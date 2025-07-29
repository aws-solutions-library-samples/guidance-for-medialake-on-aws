import React from "react";
import {
  Menu,
  MenuItem,
  FormControlLabel,
  Checkbox,
  Typography,
} from "@mui/material";

interface PipelineColumnMenuProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  visibility: Record<string, boolean>;
  onVisibilityChange: (visibility: Record<string, boolean>) => void;
}

export const PipelineColumnMenu: React.FC<PipelineColumnMenuProps> = ({
  anchorEl,
  onClose,
  visibility,
  onVisibilityChange,
}) => {
  const columns = [
    { id: "name", label: "Name" },
    { id: "description", label: "Description" },
    { id: "status", label: "Status" },
    { id: "createdAt", label: "Created At" },
  ];

  const handleToggle = (columnId: string) => {
    onVisibilityChange({
      ...visibility,
      [columnId]: !visibility[columnId],
    });
  };

  return (
    <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={onClose}>
      <Typography variant="subtitle2" sx={{ px: 2, py: 1 }}>
        Show Columns
      </Typography>
      {columns.map((column) => (
        <MenuItem key={column.id} onClick={() => handleToggle(column.id)}>
          <FormControlLabel
            control={
              <Checkbox
                checked={visibility[column.id] !== false}
                onChange={() => handleToggle(column.id)}
              />
            }
            label={column.label}
          />
        </MenuItem>
      ))}
    </Menu>
  );
};
