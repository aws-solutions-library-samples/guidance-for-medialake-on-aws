import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { createJSONEditor, Mode, JSONContent } from "vanilla-jsoneditor";
import { Box, Alert, Typography, Paper, alpha, IconButton, Tooltip, Divider } from "@mui/material";
import {
  MenuBook as DocsIcon,
  Clear as ClearIcon,
  FormatIndentIncrease as FormatIcon,
  Code as CodeIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
} from "@mui/icons-material";
import { EventBridgePatternValidator, ValidationResult } from "@/services/eventbridge-validator";

interface EventBridgePatternEditorProps {
  value: Record<string, any>;
  onChange: (pattern: Record<string, any>) => void;
  onValidationChange?: (isValid: boolean, errors: string[]) => void;
  readonly?: boolean;
}

export const EventBridgePatternEditor: React.FC<EventBridgePatternEditorProps> = ({
  value,
  onChange,
  onValidationChange,
  readonly = false,
}) => {
  const { t } = useTranslation();
  const editorRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<ReturnType<typeof createJSONEditor> | undefined>(undefined);
  const [validationResult, setValidationResult] = useState<ValidationResult>({
    valid: true,
    errors: [],
    warnings: [],
  });
  const validationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Use refs to avoid recreating the editor when callbacks change
  const onChangeRef = useRef(onChange);
  const onValidationChangeRef = useRef(onValidationChange);

  useEffect(() => {
    onChangeRef.current = onChange;
    onValidationChangeRef.current = onValidationChange;
  }, [onChange, onValidationChange]);

  useEffect(() => {
    if (!editorRef.current) return;

    const editor = createJSONEditor({
      target: editorRef.current,
      props: {
        content: { json: value },
        mode: Mode.text,
        readOnly: readonly,
        onChange: (updatedContent: JSONContent) => {
          // Clear any pending validation
          if (validationTimeoutRef.current) {
            clearTimeout(validationTimeoutRef.current);
          }

          // Get the JSON data from either json or text content
          let jsonData: Record<string, any> | null = null;

          if ("json" in updatedContent && updatedContent.json !== undefined) {
            jsonData = updatedContent.json as Record<string, any>;
          } else if ("text" in updatedContent && updatedContent.text) {
            try {
              jsonData = JSON.parse(updatedContent.text as string);
            } catch (e) {
              // Invalid JSON, skip validation and parent update
              return;
            }
          }

          if (jsonData) {
            // Update parent immediately using ref
            onChangeRef.current(jsonData);

            // Debounce validation to avoid excessive re-validation while typing
            validationTimeoutRef.current = setTimeout(() => {
              const result = EventBridgePatternValidator.validate(jsonData!);
              setValidationResult(result);

              if (onValidationChangeRef.current) {
                onValidationChangeRef.current(
                  result.valid,
                  result.errors.map((e) => e.message)
                );
              }
            }, 500); // Validate 500ms after user stops typing
          }
        },
      },
    });

    jsonEditorRef.current = editor;

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
      if (jsonEditorRef.current) {
        jsonEditorRef.current.destroy();
        jsonEditorRef.current = undefined;
      }
    };
  }, []); // Only create editor once on mount

  useEffect(() => {
    if (jsonEditorRef.current && value) {
      const currentContent = jsonEditorRef.current.get();
      // Check if content is JSONContent (has json property)
      if (
        "json" in currentContent &&
        JSON.stringify(currentContent.json) !== JSON.stringify(value)
      ) {
        jsonEditorRef.current.set({ json: value });
      }
    }
  }, [value]);

  // Immediate validation helper (used by clear and format buttons)
  const validatePattern = useCallback(
    (jsonData: Record<string, any>) => {
      const result = EventBridgePatternValidator.validate(jsonData);
      setValidationResult(result);

      if (onValidationChange) {
        onValidationChange(
          result.valid,
          result.errors.map((e) => e.message)
        );
      }
    },
    [onValidationChange]
  );

  const handleFormat = useCallback(() => {
    if (jsonEditorRef.current) {
      try {
        const currentContent = jsonEditorRef.current.get();

        // Handle both text and json content
        let jsonData: any;

        if ("json" in currentContent && currentContent.json !== undefined) {
          jsonData = currentContent.json;
        } else if ("text" in currentContent && currentContent.text) {
          try {
            jsonData = JSON.parse(currentContent.text);
          } catch (e) {
            console.error("Invalid JSON:", e);
            return;
          }
        }

        if (jsonData) {
          // Format and update the editor
          const formattedText = JSON.stringify(jsonData, null, 2);
          jsonEditorRef.current.set({ text: formattedText });
          // Just update parent, don't validate (format is just formatting)
          onChange(jsonData);
        }
      } catch (error) {
        console.error("Format error:", error);
      }
    }
  }, [onChange, validatePattern]);

  const handleClear = useCallback(() => {
    if (jsonEditorRef.current) {
      jsonEditorRef.current.set({ json: {} });
      onChange({});
      validatePattern({});
    }
  }, [onChange, validatePattern]);

  const handleOpenDocs = useCallback(() => {
    window.open(
      "https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-pattern-operators.html",
      "_blank",
      "noopener,noreferrer"
    );
  }, []);

  const handleExport = useCallback(() => {
    if (jsonEditorRef.current) {
      try {
        const currentContent = jsonEditorRef.current.get();
        let jsonData: any;

        if ("json" in currentContent && currentContent.json !== undefined) {
          jsonData = currentContent.json;
        } else if ("text" in currentContent && currentContent.text) {
          try {
            jsonData = JSON.parse(currentContent.text as string);
          } catch (e) {
            console.error("Invalid JSON:", e);
            return;
          }
        }

        if (jsonData) {
          const jsonString = JSON.stringify(jsonData, null, 2);
          const blob = new Blob([jsonString], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = "eventbridge-pattern.json";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        }
      } catch (error) {
        console.error("Export error:", error);
      }
    }
  }, []);

  const handleImport = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const content = e.target?.result as string;
          const jsonData = JSON.parse(content);

          if (jsonEditorRef.current) {
            jsonEditorRef.current.set({ json: jsonData });
            onChange(jsonData);
            validatePattern(jsonData);
          }
        } catch (error) {
          console.error("Import error:", error);
          alert("Invalid JSON file. Please select a valid JSON file.");
        }
      };
      reader.readAsText(file);

      // Reset input so same file can be selected again
      event.target.value = "";
    },
    [onChange, validatePattern]
  );

  return (
    <Box>
      <Paper
        elevation={0}
        sx={(theme) => ({
          mb: 1,
          p: 1,
          display: "flex",
          alignItems: "center",
          gap: 1,
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
          backgroundColor: theme.palette.background.paper,
        })}
      >
        <Tooltip title={t("pipelines.eventBridgeEditor.patternOperatorsGuide")}>
          <IconButton
            size="small"
            onClick={handleOpenDocs}
            sx={(theme) => ({
              color: theme.palette.info.main,
              "&:hover": {
                backgroundColor: alpha(theme.palette.info.main, 0.1),
              },
            })}
          >
            <DocsIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title={t("pipelines.eventBridgeEditor.formatJson")}>
          <IconButton
            size="small"
            onClick={handleFormat}
            sx={(theme) => ({
              color: theme.palette.primary.main,
              "&:hover": {
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
              },
            })}
          >
            <FormatIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        <Tooltip title={t("pipelines.eventBridgeEditor.exportToJson")}>
          <IconButton
            size="small"
            onClick={handleExport}
            sx={(theme) => ({
              color: theme.palette.secondary.main,
              "&:hover": {
                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
              },
            })}
          >
            <DownloadIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title={t("pipelines.eventBridgeEditor.importFromJson")}>
          <IconButton
            size="small"
            onClick={handleImport}
            sx={(theme) => ({
              color: theme.palette.secondary.main,
              "&:hover": {
                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
              },
            })}
          >
            <UploadIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {/* Hidden file input for import */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        <Tooltip title="Clear">
          <IconButton
            size="small"
            onClick={handleClear}
            sx={(theme) => ({
              color: theme.palette.error.main,
              "&:hover": {
                backgroundColor: alpha(theme.palette.error.main, 0.1),
              },
            })}
          >
            <ClearIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Box sx={{ flexGrow: 1 }} />

        <Typography
          variant="caption"
          sx={(theme) => ({
            color: theme.palette.text.secondary,
            display: "flex",
            alignItems: "center",
            gap: 0.5,
          })}
        >
          <CodeIcon fontSize="small" />
          EventBridge Pattern
        </Typography>
      </Paper>

      <Paper
        elevation={0}
        sx={(theme) => ({
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
          overflow: "hidden",
          "& .jse-main": {
            backgroundColor: theme.palette.background.paper,
            border: "none",
          },
          "& .jse-menu": {
            display: "none",
          },
          "& .jse-button": {
            backgroundColor: "transparent",
            border: "none",
            color: theme.palette.primary.contrastText,
            borderRadius: theme.shape.borderRadius,
            padding: "6px 12px",
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.dark, 0.8),
            },
            "&.jse-selected": {
              backgroundColor: alpha(theme.palette.primary.dark, 0.6),
            },
          },
          "& .jse-separator": {
            borderColor: alpha(theme.palette.primary.contrastText, 0.2),
          },
          "& .cm-editor": {
            backgroundColor: theme.palette.background.paper,
            color: theme.palette.text.primary,
          },
          "& .cm-gutters": {
            backgroundColor: theme.palette.background.default,
            borderRight: `1px solid ${theme.palette.divider}`,
            color: theme.palette.text.secondary,
          },
          "& .cm-activeLineGutter": {
            backgroundColor: alpha(theme.palette.primary.main, 0.1),
          },
          "& .cm-lineNumbers .cm-gutterElement": {
            color: theme.palette.text.secondary,
          },
          "& .cm-content": {
            caretColor: theme.palette.primary.main,
          },
          "& .cm-cursor": {
            borderLeftColor: theme.palette.primary.main,
          },
          "& .cm-selectionBackground": {
            backgroundColor: alpha(theme.palette.primary.main, 0.2),
          },
          "& .cm-focused .cm-selectionBackground": {
            backgroundColor: alpha(theme.palette.primary.main, 0.3),
          },
          "& .jse-statusbar": {
            backgroundColor: theme.palette.background.default,
            borderTop: `1px solid ${theme.palette.divider}`,
            color: theme.palette.text.secondary,
            fontSize: "0.75rem",
          },
          "& .ͼ1 .cm-line": {
            color: theme.palette.text.primary,
          },
          "& .ͼ2": {
            color: theme.palette.success.main,
          },
          "& .ͼ3": {
            color: theme.palette.info.main,
          },
          "& .ͼ4": {
            color: theme.palette.warning.main,
          },
          "& .ͼ5": {
            color: theme.palette.secondary.main,
          },
          // Style editor message notifications (format prompt, syntax errors, etc.)
          "& .jse-message": {
            borderRadius: "0 !important",
            padding: theme.spacing(1.5),
            margin: theme.spacing(1),
            fontSize: "0.875rem",
            border: "none !important",
          },
          "& .jse-message.jse-info": {
            backgroundColor: `${alpha(theme.palette.success.main, 0.1)} !important`,
            color: `${theme.palette.success.dark} !important`,
            borderLeft: `4px solid ${theme.palette.success.main} !important`,
          },
          "& .jse-message.jse-warning": {
            backgroundColor: `${alpha(theme.palette.warning.main, 0.1)} !important`,
            color: `${theme.palette.warning.dark} !important`,
            borderLeft: `4px solid ${theme.palette.warning.main} !important`,
          },
          "& .jse-message.jse-error": {
            backgroundColor: `${alpha(theme.palette.error.main, 0.1)} !important`,
            color: `${theme.palette.error.dark} !important`,
            borderLeft: `4px solid ${theme.palette.error.main} !important`,
          },
          "& .jse-message .jse-button": {
            backgroundColor: "transparent !important",
            border: `1px solid currentColor !important`,
            borderRadius: `${theme.shape.borderRadius}px !important`,
            padding: `${theme.spacing(0.5, 1.5)} !important`,
            fontSize: "0.813rem !important",
            fontWeight: "500 !important",
            cursor: "pointer",
            transition: "all 0.2s ease",
            color: "inherit !important",
          },
          "& .jse-message.jse-info .jse-button": {
            color: `${theme.palette.success.main} !important`,
            "&:hover": {
              backgroundColor: `${alpha(theme.palette.success.main, 0.1)} !important`,
            },
          },
          "& .jse-message.jse-error .jse-button": {
            color: `${theme.palette.error.main} !important`,
            "&:hover": {
              backgroundColor: `${alpha(theme.palette.error.main, 0.1)} !important`,
            },
          },
          "& .jse-message .jse-text": {
            color: "inherit !important",
          },
          // Hide icons in message buttons
          "& .jse-message .jse-button svg": {
            display: "none !important",
          },
        })}
      >
        <Box
          ref={editorRef}
          sx={{
            height: "400px",
          }}
        />
      </Paper>

      {validationResult.errors.length > 0 && (
        <Alert severity="error" sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: "bold", mb: 1 }}>
            Validation Errors:
          </Typography>
          {validationResult.errors.map((error, index) => (
            <Box key={index} sx={{ mb: 0.5 }}>
              • <strong>{error.path}:</strong> {error.message}
            </Box>
          ))}
        </Alert>
      )}

      {validationResult.warnings.length > 0 && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: "bold", mb: 1 }}>
            Warnings:
          </Typography>
          {validationResult.warnings.map((warning, index) => (
            <Box key={index} sx={{ mb: 0.5 }}>
              • {warning.message}
            </Box>
          ))}
        </Alert>
      )}
    </Box>
  );
};
