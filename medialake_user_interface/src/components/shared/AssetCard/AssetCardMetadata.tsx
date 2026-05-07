/**
 * AssetCardMetadata — renders the metadata fields grid for the full variant.
 * Includes inline name editing support.
 */
import React, { useRef } from "react";
import { Box, Typography, IconButton, CircularProgress } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { InlineTextEditor } from "../../common/InlineTextEditor";
import InlineEditActions from "../../common/InlineEditActions";
import type { AssetField } from "@/types/shared/assetComponents";

interface AssetCardMetadataProps {
  id: string;
  fields: AssetField[];
  renderField: (fieldId: string) => string | React.ReactNode;
  isEditing?: boolean;
  editedName?: string;
  isRenaming: boolean;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean, value?: string) => void;
}

const AssetCardMetadata: React.FC<AssetCardMetadataProps> = React.memo(
  ({
    id,
    fields,
    renderField,
    isEditing,
    editedName,
    isRenaming,
    onEditClick,
    onEditNameChange,
    onEditNameComplete,
  }) => {
    const preventCommitRef = useRef(false);
    const commitRef = useRef<(() => void) | null>(null);

    return (
      <Box sx={{ px: 1.5, pt: 1.5, pb: 1.5 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
          {fields.map((field) => (
            <Box
              key={field.id}
              sx={{
                display: "grid",
                gridTemplateColumns: "80px 1fr",
                alignItems: "center",
                width: "100%",
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ flexShrink: 0, pr: 1, fontSize: "0.75rem" }}
              >
                {field.label}:
              </Typography>
              {field.id === "name" && onEditClick ? (
                isEditing ? (
                  <Box
                    sx={{
                      gridColumn: "1 / span 2",
                      display: "flex",
                      flexDirection: "column",
                      gap: 1,
                      width: "100%",
                      mt: 1,
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <InlineTextEditor
                      initialValue={editedName || ""}
                      editingCellId={id}
                      preventCommitRef={preventCommitRef}
                      commitRef={commitRef}
                      onChangeCommit={(value) =>
                        onEditNameChange?.({
                          target: { value },
                        } as React.ChangeEvent<HTMLInputElement>)
                      }
                      onComplete={(save, value) => onEditNameComplete?.(save, value)}
                      isEditing
                      disabled={isRenaming}
                      autoFocus
                      size="small"
                      fullWidth
                      multiline
                      rows={2}
                      sx={{
                        width: "100%",
                        "& .MuiInputBase-root": { width: "100%" },
                        "& .MuiInputBase-input": { whiteSpace: "normal", wordBreak: "break-word" },
                      }}
                      InputProps={{ endAdornment: isRenaming && <CircularProgress size={16} /> }}
                    />
                    <InlineEditActions
                      preventCommitRef={preventCommitRef}
                      commitRef={commitRef}
                      onCancel={() => onEditNameComplete?.(false, undefined)}
                      isDisabled={isRenaming}
                    />
                  </Box>
                ) : (
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      width: "100%",
                      justifyContent: "space-between",
                    }}
                  >
                    <Typography
                      variant="body2"
                      title={String(renderField(field.id))}
                      sx={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "normal",
                        wordBreak: "break-word",
                        flexGrow: 1,
                        userSelect: "text",
                        maxHeight: "2.4em",
                        lineHeight: "1.2em",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        "&:hover": { maxHeight: "none", WebkitLineClamp: "unset" },
                      }}
                    >
                      {renderField(field.id)}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditClick(e);
                      }}
                      disabled={isRenaming}
                    >
                      {isRenaming ? <CircularProgress size={16} /> : <EditIcon fontSize="small" />}
                    </IconButton>
                  </Box>
                )
              ) : (
                <Typography
                  variant="body2"
                  title={String(renderField(field.id))}
                  sx={{
                    userSelect: "text",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "normal",
                    wordBreak: "break-word",
                    width: "100%",
                    maxHeight: "2.4em",
                    lineHeight: "1.2em",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    "&:hover": { maxHeight: "none", WebkitLineClamp: "unset" },
                  }}
                >
                  {renderField(field.id)}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      </Box>
    );
  }
);

AssetCardMetadata.displayName = "AssetCardMetadata";
export default AssetCardMetadata;
