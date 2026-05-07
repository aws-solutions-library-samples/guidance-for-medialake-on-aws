import React from "react";
import {
  Box,
  TextField,
  Select,
  MenuItem,
  Switch,
  IconButton,
  Button,
  FormControlLabel,
} from "@mui/material";
import {
  DragIndicator as DragIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
} from "@mui/icons-material";
import type { PortalMetadataField } from "@/api/types/api.types";

interface Props {
  fields: PortalMetadataField[];
  onChange: (fields: PortalMetadataField[]) => void;
  fieldErrors?: string[];
}

const MetadataFieldBuilder: React.FC<Props> = ({ fields, onChange, fieldErrors }) => {
  const dragItem = React.useRef<number | null>(null);

  const addField = () => {
    onChange([...fields, { label: "", type: "text", required: false, order: fields.length }]);
  };

  const updateField = (i: number, updates: Partial<PortalMetadataField>) => {
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...updates } : f)));
  };

  const removeField = (i: number) => {
    onChange(fields.filter((_, idx) => idx !== i).map((f, idx) => ({ ...f, order: idx })));
  };

  const handleDragStart = (i: number) => {
    dragItem.current = i;
  };

  const handleDrop = (targetIndex: number) => {
    const srcIndex = dragItem.current;
    if (srcIndex === null || srcIndex === targetIndex) return;
    const updated = [...fields];
    const [moved] = updated.splice(srcIndex, 1);
    updated.splice(targetIndex, 0, moved);
    onChange(updated.map((f, idx) => ({ ...f, order: idx })));
    dragItem.current = null;
  };

  return (
    <Box>
      {fields.map((field, i) => (
        <Box
          key={i}
          draggable
          onDragStart={() => handleDragStart(i)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => handleDrop(i)}
          sx={{ display: "flex", gap: 1, mb: 1, alignItems: "center" }}
        >
          <DragIcon sx={{ cursor: "grab", color: "text.secondary" }} />
          <TextField
            label="Label"
            size="small"
            value={field.label}
            onChange={(e) => updateField(i, { label: e.target.value })}
            sx={{ flex: 1 }}
            error={!!fieldErrors?.[i]}
            helperText={fieldErrors?.[i]}
          />
          <Select
            size="small"
            value={field.type}
            onChange={(e) =>
              updateField(i, { type: e.target.value as PortalMetadataField["type"] })
            }
            sx={{ width: 120 }}
          >
            <MenuItem value="text">Text</MenuItem>
            <MenuItem value="email">Email</MenuItem>
            <MenuItem value="number">Number</MenuItem>
            <MenuItem value="select">Select</MenuItem>
          </Select>
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={field.required}
                onChange={(_, checked) => updateField(i, { required: checked })}
              />
            }
            label="Req"
          />
          <IconButton size="small" onClick={() => removeField(i)}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      ))}
      <Button size="small" startIcon={<AddIcon />} onClick={addField}>
        Add Field
      </Button>
    </Box>
  );
};

export default MetadataFieldBuilder;
