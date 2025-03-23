import React from 'react';
import { Box, Typography, IconButton, TextField, Button, CircularProgress } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditIcon from '@mui/icons-material/Edit';
import { AssetAudio } from '../asset';

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
    isRenaming?: boolean;
    renderField: (fieldId: string) => string | React.ReactNode;
    onAssetClick: () => void;
    onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
    onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
    placeholderImage?: string;
    onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
    isEditing?: boolean;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onEditNameComplete?: (save: boolean) => void;
    cardSize?: 'small' | 'medium' | 'large';
    aspectRatio?: 'vertical' | 'square' | 'horizontal';
    thumbnailScale?: 'fit' | 'fill';
    showMetadata?: boolean;
}

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
    isRenaming = false,
    isEditing,
    editedName,
    onEditNameChange,
    onEditNameComplete,
    cardSize = 'medium',
    aspectRatio = 'square',
    thumbnailScale = 'fill',
    showMetadata = true,
}) => {
 
    const [selectionRange, setSelectionRange] = React.useState<[number, number] | null>(null);
    const inputRef = React.useRef<HTMLInputElement | null>(null);

    // Determine the card dimensions based on props
    const getCardDimensions = () => {
        const baseHeight = aspectRatio === 'vertical' ? 300
            : aspectRatio === 'square' ? 200
            : aspectRatio === 'horizontal' ? 150
            : 200;

        const sizeMultiplier = cardSize === 'small' ? 0.8
            : cardSize === 'large' ? 1.2
            : 1;

        return {
            height: baseHeight * sizeMultiplier,
            width: '100%',
        };
    };
    const dimensions = getCardDimensions();

    // Fallback image error
    const defaultImageErrorHandler = (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
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

console.log("isRenaming",isRenaming)
    React.useEffect(() => {
        if (isEditing && inputRef.current) {
            // Move caret to the beginning of the string
            inputRef.current.focus();
            inputRef.current.setSelectionRange(0, 0);
            setSelectionRange([0, 0]);
        }
    }, [isEditing]);


    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // Remember where the user was typing
        const start = e.target.selectionStart ?? 0;
        const end = e.target.selectionEnd ?? start;
        onEditNameChange?.(e);
        setSelectionRange([start, end]);
    };


    React.useEffect(() => {
        if (isEditing && inputRef.current && selectionRange) {
            // After the new value is in place, reset selection
            inputRef.current.setSelectionRange(selectionRange[0], selectionRange[1]);
        }
    }, [isEditing, editedName, selectionRange]);

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
                {/* Render appropriate content based on asset type */}
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
                    />
                ) : assetType === 'Audio' ? (
                    <Box
                        onClick={onAssetClick}
                        sx={{
                            cursor: 'pointer',
                            width: dimensions.width,
                            height: dimensions.height,
                            backgroundColor: 'rgba(0,0,0,0.03)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            overflow: 'hidden'
                        }}
                    >
                        <AssetAudio 
                            src={proxyUrl || ''} 
                            alt={name}
                            compact={true}
                        />
                    </Box>
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

                {/* Metadata (non-clickable) */}
                {showMetadata ? (
                    <Box sx={{ p: 2 }}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            {fields.map((field) =>
                                field.visible && (
                                    <Box key={field.id}>
                                        <Typography variant="caption" color="text.secondary">
                                            {field.label}:
                                        </Typography>
                                        {field.id === 'name' && onEditClick ? (
                                            isEditing ? (
                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                                    <TextField
                                                        inputRef={inputRef}
                                                        value={editedName}
                                                        disabled={isRenaming}
                                                        onChange={handleInputChange}
                                                        onKeyPress={(e) => {
                                                            if (e.key === 'Enter') {
                                                                onEditNameComplete?.(true);
                                                            } else if (e.key === 'Escape') {
                                                                onEditNameComplete?.(false);
                                                            }
                                                        }}
                                                        onClick={(e) => e.stopPropagation()}
                                                        autoFocus
                                                        size="small"
                                                        fullWidth
                                                        InputProps={{
                                                            endAdornment: isRenaming && (
                                                              <CircularProgress size={16} />
                                                            )
                                                          }}
                                                    />
                                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                                        <Button
                                                            size="small"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                onEditNameComplete?.(true);
                                                            }}
                                                            variant="contained"
                                                            disabled={isRenaming}
                                                        >
                                                            Save
                                                        </Button>
                                                        <Button
                                                            size="small"
                                                            disabled={isRenaming}
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                onEditNameComplete?.(false);
                                                            }}
                                                        >
                                                            Cancel
                                                        </Button>
                                                    </Box>
                                                </Box>
                                            ) : (
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Typography
                                                        sx={{
                                                            wordBreak: 'break-word',
                                                            userSelect: 'text', // Allow text selection
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
                    // If showMetadata = false, place action buttons as overlay
                    <Box
                        sx={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 1 }}
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
