import React, { useRef, useCallback } from "react";
import { Box, TextField, IconButton, Button, Typography } from "@mui/material";
import { DeleteOutline as DeleteOutlineIcon, Add as AddIcon } from "@mui/icons-material";

interface KeyValueEditorProps {
  rows: Array<{ key: string; value: string; id?: string }>;
  onChange: (rows: Array<{ key: string; value: string; id?: string }>) => void;
  label?: string;
}

let nextId = 0;
const generateId = () => `kv-${++nextId}-${Date.now()}`;

export const KeyValueEditor: React.FC<KeyValueEditorProps> = ({ rows, onChange, label }) => {
  // Assign stable IDs to rows that don't have them
  const rowsWithIds = useRef<Map<number, string>>(new Map());

  const getRowId = useCallback(
    (row: { key: string; value: string; id?: string }, index: number): string => {
      if (row.id) return row.id;
      if (!rowsWithIds.current.has(index)) {
        rowsWithIds.current.set(index, generateId());
      }
      return rowsWithIds.current.get(index)!;
    },
    []
  );

  const handleKeyChange = (index: number, newKey: string) => {
    const updated = rows.map((row, i) => (i === index ? { ...row, key: newKey } : row));
    onChange(updated);
  };

  const handleValueChange = (index: number, newValue: string) => {
    const updated = rows.map((row, i) => (i === index ? { ...row, value: newValue } : row));
    onChange(updated);
  };

  const handleRemoveRow = (index: number) => {
    rowsWithIds.current.delete(index);
    const updated = rows.filter((_, i) => i !== index);
    onChange(updated);
  };

  const handleAddRow = () => {
    const newRow = { key: "", value: "", id: generateId() };
    onChange([...rows, newRow]);
  };

  return (
    <Box>
      {label && (
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            fontSize: "0.75rem",
            color: "text.secondary",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            mb: 0.8,
            display: "block",
          }}
        >
          {label}
        </Typography>
      )}
      {rows.map((row, index) => (
        <Box
          key={row.id || getRowId(row, index)}
          sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}
        >
          <TextField
            size="small"
            placeholder="Key"
            value={row.key}
            onChange={(e) => handleKeyChange(index, e.target.value)}
            sx={{ flex: 1, "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
            inputProps={{ "aria-label": `Metadata key ${index}` }}
          />
          <TextField
            size="small"
            placeholder="Value"
            value={row.value}
            onChange={(e) => handleValueChange(index, e.target.value)}
            sx={{ flex: 1, "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
            inputProps={{ "aria-label": `Metadata value ${index}` }}
          />
          <IconButton
            size="small"
            onClick={() => handleRemoveRow(index)}
            aria-label={`Remove metadata row ${index}`}
            sx={{ color: "text.secondary" }}
          >
            <DeleteOutlineIcon fontSize="small" />
          </IconButton>
        </Box>
      ))}
      <Button
        size="small"
        startIcon={<AddIcon />}
        onClick={handleAddRow}
        sx={{ textTransform: "none", fontWeight: 500, fontSize: "0.82rem" }}
      >
        Add Row
      </Button>
    </Box>
  );
};
