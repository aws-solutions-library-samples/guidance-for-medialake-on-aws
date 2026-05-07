import React, { useState, useEffect, useMemo } from "react";
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  InputAdornment,
} from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";
import type { PortalMetadataField } from "../types/portal.types";

interface Props {
  fields: PortalMetadataField[];
  prePopulatedValues: Record<string, string>;
  onChange: (values: Record<string, string>, isValid: boolean) => void;
}

const PortalMetadataForm: React.FC<Props> = ({ fields, prePopulatedValues, onChange }) => {
  // Memoize the sorted array so `sorted` is stable across renders and
  // doesn't cause the `useEffect` below to re-run on every render.
  const sorted = useMemo(
    () => [...fields].sort((a, b) => a.order - b.order),
    [fields],
  );
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    sorted.forEach((f) => {
      init[f.label] = prePopulatedValues[f.label] || "";
    });
    return init;
  });
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const isValid = sorted
      .filter((f) => f.required)
      .every((f) => (values[f.label] || "").trim().length > 0);
    onChange(values, isValid);
  }, [values, sorted, onChange]);

  const handleChange = (label: string, val: string) => {
    setValues((prev) => ({ ...prev, [label]: val }));
  };

  const handleBlur = (label: string) => {
    setTouched((prev) => ({ ...prev, [label]: true }));
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      {sorted.map((field) => {
        const val = values[field.label] || "";
        const isPrePopulated = field.label in prePopulatedValues;
        const showError = field.required && touched[field.label] && !val.trim();

        if (field.type === "select") {
          return (
            <FormControl key={field.label} fullWidth size="small" error={showError}>
              <InputLabel required={field.required}>{field.label}</InputLabel>
              <Select
                value={val}
                label={field.label}
                onChange={(e) => handleChange(field.label, e.target.value)}
                readOnly={isPrePopulated}
                onBlur={() => handleBlur(field.label)}
              >
                {(field.options || []).map((opt) => (
                  <MenuItem key={opt} value={opt}>
                    {opt}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          );
        }

        return (
          <TextField
            key={field.label}
            label={field.label}
            type={field.type}
            value={val}
            onChange={(e) => handleChange(field.label, e.target.value)}
            onBlur={() => handleBlur(field.label)}
            required={field.required}
            error={showError}
            helperText={showError ? "This field is required" : undefined}
            size="small"
            fullWidth
            slotProps={{
              input: {
                readOnly: isPrePopulated,
                ...(isPrePopulated && {
                  endAdornment: (
                    <InputAdornment position="end">
                      <LockIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }),
              },
            }}
          />
        );
      })}
    </Box>
  );
};

export default PortalMetadataForm;
