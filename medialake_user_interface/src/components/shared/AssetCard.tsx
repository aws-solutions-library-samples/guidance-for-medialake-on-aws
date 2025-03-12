import React, { useState, useRef, useEffect } from 'react';
import { Box, Typography, IconButton, TextField, Button } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditIcon from '@mui/icons-material/Edit';

export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

export interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType?: string;
  fields: AssetField[];
  renderField: (fieldId: string) => string | React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  placeholderImage?: string;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  isEditing?: boolean;
  editedName?: string;
  /**
   * Callback when renaming is complete.
   * The first argument indicates whether to save (true) or cancel (false).
   * The second argument provides the new name (if saving).
   */
  onEditNameComplete?: (save: boolean, newName?: string) => void;
  cardSize?: 'small' | 'medium' | 'large';
  aspectRatio?: 'vertical' | 'square' | 'horizontal';
  thumbnailScale?: 'fit' | 'fill';
  showMetadata?: boolean;
}

/**
 * RenamingField component manages its own local state so that typing does not force
 * a re-render from the parent that resets the cursor position.
 */
interface RenamingFieldProps {
  initialName: string;
  onEditNameComplete?: (save: boolean, newName?: string) => void;
}

const RenamingField: React.FC<RenamingFieldProps> = React.memo(
    ({ initialName, onEditNameComplete }) => {
      const [localName, setLocalName] = useState(initialName);
      const inputRef = useRef<HTMLInputElement>(null);
  
      useEffect(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          // Set the caret at the beginning of the input field.
          inputRef.current.setSelectionRange(0, 0);
        }
      }, []);
  
      useEffect(() => {
        setLocalName(initialName);
      }, [initialName]);
  
      const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setLocalName(e.target.value);
      };
  
      const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
          onEditNameComplete?.(true, localName);
        } else if (e.key === 'Escape') {
          onEditNameComplete?.(false, localName);
        }
      };
  
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <TextField
            inputRef={inputRef}
            value={localName}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            size="small"
            fullWidth
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onEditNameComplete?.(true, localName);
              }}
              variant="contained"
            >
              Save
            </Button>
            <Button
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onEditNameComplete?.(false, localName);
              }}
            >
              Cancel
            </Button>
          </Box>
        </Box>
      );
    }
  );
  
const AssetCard: React.FC<AssetCardProps> = ({
  id,
  name,
  thumbnailUrl,
  proxyUrl,
  assetType,
  fields,
  renderField,
  onAssetClick,
  onDeleteClick,
  onMenuClick,
  onEditClick,
  placeholderImage = 'https://placehold.co/300x200?text=Placeholder',
  onImageError,
  isEditing,
  editedName,
  onEditNameComplete,
  cardSize = 'medium',
  aspectRatio = 'square',
  thumbnailScale = 'fill',
  showMetadata = true,
}) => {
  const getCardDimensions = () => {
    const baseHeight =
      aspectRatio === 'vertical'
        ? 300
        : aspectRatio === 'square'
        ? 200
        : aspectRatio === 'horizontal'
        ? 150
        : 200;

    const sizeMultiplier =
      cardSize === 'small' ? 0.8 : cardSize === 'large' ? 1.2 : 1;

    return {
      height: baseHeight * sizeMultiplier,
      width: '100%',
    };
  };

  const dimensions = getCardDimensions();
  const defaultImageErrorHandler = (
    event: React.SyntheticEvent<HTMLImageElement, Event>
  ) => {
    event.currentTarget.src = placeholderImage;
  };

  const handleDeleteClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    onDeleteClick(event);
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    onMenuClick(event);
  };

  return (
    <Box
      sx={{
        position: 'relative',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          transform: 'translateY(-4px)',
        },
      }}
    >
      <Box
        sx={{
          borderRadius: 2,
          overflow: 'hidden',
          bgcolor: 'background.paper',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          '&:hover': {
            boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
          },
        }}
      >
        {assetType === 'Video' ? (
          <video
            onClick={(event) => {
              event.preventDefault();
              onAssetClick();
            }}
            style={{
              width: dimensions.width,
              height: dimensions.height,
              backgroundColor: 'rgba(0,0,0,0.03)',
              objectFit: 'cover',
            }}
            controls
            src={proxyUrl}
          ></video>
        ) : (
          <Box
            onClick={onAssetClick}
            component="img"
            src={thumbnailUrl || placeholderImage}
            alt={name}
            onError={onImageError || defaultImageErrorHandler}
            data-image-id={id}
            sx={{
              cursor: 'pointer',
              width: dimensions.width,
              height: dimensions.height,
              backgroundColor: 'rgba(0,0,0,0.03)',
              objectFit: thumbnailScale === 'fit' ? 'contain' : 'cover',
              transition: 'all 0.2s ease-in-out',
            }}
          />
        )}

        {showMetadata ? (
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {fields.map(
                (field) =>
                  field.visible && (
                    <Box key={field.id}>
                      <Typography variant="caption" color="text.secondary">
                        {field.label}:
                      </Typography>
                      {field.id === 'name' && onEditClick ? (
                        isEditing ? (
                          <RenamingField
                            initialName={editedName || name}
                            onEditNameComplete={onEditNameComplete}
                          />
                        ) : (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                            }}
                          >
                            <Typography
                              sx={{
                                wordBreak: 'break-word',
                                userSelect: 'text',
                              }}
                              display="inline"
                              variant="body2"
                            >
                              {renderField(field.id)}
                            </Typography>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                onEditClick(e);
                              }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        )
                      ) : (
                        <Typography variant="body2" sx={{ userSelect: 'text' }}>
                          {renderField(field.id)}
                        </Typography>
                      )}
                    </Box>
                  )
              )}
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 1,
                  mt: 1,
                }}
              >
                <IconButton size="small" onClick={handleDeleteClick}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" onClick={handleMenuClick}>
                  <MoreVertIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          </Box>
        ) : (
          <Box
            sx={{
              position: 'absolute',
              top: 8,
              right: 8,
              display: 'flex',
              gap: 1,
            }}
          >
            <IconButton
              size="small"
              onClick={handleDeleteClick}
              sx={{ bgcolor: 'rgba(255,255,255,0.8)' }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={handleMenuClick}
              sx={{ bgcolor: 'rgba(255,255,255,0.8)' }}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AssetCard;
