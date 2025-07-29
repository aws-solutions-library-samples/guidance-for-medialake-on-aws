import React from "react";
import { Controller, Control, FieldValues, Path } from "react-hook-form";
import {
  FormControl,
  InputLabel,
  MenuItem,
  Chip,
  Box,
  OutlinedInput,
  FormHelperText,
  Tooltip,
  IconButton,
  InputAdornment,
} from "@mui/material";
import Select, { SelectProps } from "@mui/material/Select";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { useTranslation } from "react-i18next";

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
      width: 250,
    },
  },
};

export type FormSelectProps<T extends FieldValues> = {
  name: Path<T>;
  control: Control<T>;
  label: string;
  options: Array<{ label: string; value: string }>;
  multiple?: boolean;
  required?: boolean;
  fullWidth?: boolean;
  tooltip?: string;
  translationPrefix?: string;
  showHelper?: boolean;
} & Omit<
  SelectProps<string | string[]>,
  "name" | "multiple" | "value" | "onChange"
>;

export const FormSelect = <T extends FieldValues>({
  name,
  control,
  label,
  options,
  multiple = false,
  required = false,
  fullWidth = true,
  tooltip,
  translationPrefix,
  showHelper = false,
  ...rest
}: FormSelectProps<T>) => {
  const { t } = useTranslation();

  // Handle translations
  const translatedLabel = translationPrefix
    ? t(`${translationPrefix}.fields.${name}.label`, label)
    : label;

  const translatedTooltip =
    translationPrefix && tooltip
      ? t(`${translationPrefix}.fields.${name}.tooltip`, tooltip)
      : tooltip;

  const translatedHelperText =
    translationPrefix && showHelper
      ? t(`${translationPrefix}.fields.${name}.helper`, "")
      : undefined;

  // Translate option labels if translationPrefix is provided
  const translatedOptions = options.map((option) => ({
    ...option,
    label: translationPrefix
      ? t(
          `${translationPrefix}.fields.${name}.options.${option.value}`,
          option.label,
        )
      : option.label,
  }));

  const tooltipIcon = translatedTooltip && (
    <InputAdornment position="end">
      <Tooltip title={translatedTooltip} arrow>
        <IconButton
          size="small"
          aria-label={t("common.moreInfo", "More information")}
          tabIndex={-1}
        >
          <HelpOutlineIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </InputAdornment>
  );

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <FormControl
          fullWidth={fullWidth}
          error={!!error}
          required={required}
          variant="outlined"
        >
          <InputLabel>{translatedLabel}</InputLabel>
          <Select<string | string[]>
            {...field}
            {...rest}
            multiple={multiple}
            variant="outlined"
            input={
              <OutlinedInput
                label={translatedLabel}
                endAdornment={tooltipIcon}
              />
            }
            renderValue={(selected) => {
              if (multiple) {
                return (
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                    {(selected as string[]).map((value) => (
                      <Chip
                        key={value}
                        label={
                          translatedOptions.find((opt) => opt.value === value)
                            ?.label || value
                        }
                      />
                    ))}
                  </Box>
                );
              }
              return (
                translatedOptions.find((opt) => opt.value === selected)
                  ?.label || (selected as string)
              );
            }}
            MenuProps={MenuProps}
          >
            {translatedOptions.map(({ label, value }) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </Select>
          {(error || (showHelper && translatedHelperText)) && (
            <FormHelperText>
              {error
                ? translationPrefix
                  ? t(
                      `${translationPrefix}.errors.${error.type}`,
                      error.message || "",
                    )
                  : error.message
                : translatedHelperText}
            </FormHelperText>
          )}
        </FormControl>
      )}
    />
  );
};
