import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Box,
  TextField,
  InputAdornment,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import LockIcon from "@mui/icons-material/Lock";
import { format, parse, isValid } from "date-fns";
import type { PathSegmentRule } from "../types/portal.types";

/** Extended segment fields that may be present on segments created with the Rule Builder. */
interface ExtendedPathSegment extends PathSegmentRule {
  segmentType?: "text" | "alphanumeric" | "numbers" | "date" | "list" | "pattern";
  listValues?: string[];
}

interface Props {
  pathSegments: PathSegmentRule[];
  prePopulatedValues: Record<string, string>;
  onChange: (constructedPath: string, isValid: boolean) => void;
  /** Separator used to join segment values. Defaults to "/". */
  pathSeparator?: string;
}

const PortalPathBuilder: React.FC<Props> = ({
  pathSegments,
  prePopulatedValues,
  onChange,
  pathSeparator = "/",
}) => {
  // Memoize `sorted` so the `useEffect` below only re-runs when the
  // underlying `pathSegments` reference actually changes.
  const sorted = useMemo(
    () => [...pathSegments].sort((a, b) => a.position - b.position),
    [pathSegments],
  );
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    sorted.forEach((seg) => {
      init[seg.label] = prePopulatedValues[seg.label] || "";
    });
    return init;
  });

  useEffect(() => {
    const allValid = sorted.every((seg) => {
      const val = values[seg.label] || "";
      return val.length > 0 && new RegExp(seg.regex).test(val);
    });
    const path = sorted.map((seg) => values[seg.label] || "").join(pathSeparator);
    onChange(path, allValid);
  }, [values, sorted, onChange, pathSeparator]);

  const handleChange = useCallback((label: string, val: string) => {
    setValues((prev) => ({ ...prev, [label]: val }));
  }, []);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {sorted.map((seg) => {
          const extSeg = seg as ExtendedPathSegment;
          const val = values[seg.label] || "";
          const isPrePopulated = seg.label in prePopulatedValues;
          const hasError = val.length > 0 && !new RegExp(seg.regex).test(val);
          const segType = extSeg.segmentType;

          // Date segment → DatePicker
          if (segType === "date" && !isPrePopulated) {
            const dateValue = val ? parse(val, "yyyy-MM-dd", new Date()) : null;
            const isValidDate = dateValue && isValid(dateValue);

            return (
              <DatePicker
                key={seg.label}
                label={seg.label}
                value={isValidDate ? dateValue : null}
                onChange={(newDate) => {
                  if (newDate && isValid(newDate)) {
                    handleChange(seg.label, format(newDate, "yyyy-MM-dd"));
                  } else {
                    handleChange(seg.label, "");
                  }
                }}
                format="yyyy-MM-dd"
                slotProps={{
                  textField: {
                    size: "small",
                    fullWidth: true,
                    error: hasError,
                    helperText: hasError ? "Must be a valid date (YYYY-MM-DD)" : undefined,
                  },
                }}
              />
            );
          }

          // List segment → Select dropdown
          if (segType === "list" && extSeg.listValues?.length && !isPrePopulated) {
            return (
              <FormControl key={seg.label} fullWidth size="small" error={hasError}>
                <InputLabel>{seg.label}</InputLabel>
                <Select
                  value={val}
                  label={seg.label}
                  onChange={(e) => handleChange(seg.label, e.target.value)}
                >
                  {extSeg.listValues!.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            );
          }

          // Default: TextField (text, alphanumeric, numbers, pattern, or fallback)
          return (
            <TextField
              key={seg.label}
              label={seg.label}
              value={val}
              onChange={(e) => handleChange(seg.label, e.target.value)}
              error={hasError}
              helperText={hasError ? `Must match pattern: ${seg.regex}` : undefined}
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
    </LocalizationProvider>
  );
};

export default PortalPathBuilder;
