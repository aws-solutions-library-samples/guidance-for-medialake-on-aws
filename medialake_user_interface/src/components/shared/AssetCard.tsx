import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, IconButton, TextField, Button, CircularProgress, Checkbox } from '@mui/material';
import { alpha } from '@mui/material/styles';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditIcon from '@mui/icons-material/Edit';
import FavoriteIcon from '@mui/icons-material/Favorite';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
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
    menuOpen?: boolean; // Add prop to track menu state from parent
    isFavorite?: boolean; // Whether the asset is favorited
    onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void; // Callback when favorite is toggled
    isSelected?: boolean; // Whether the asset is selected for bulk operations
    onSelectToggle?: (id: string, event: React.MouseEvent<HTMLElement>) => void; // Callback when selection is toggled
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
    menuOpen = false, // Default to false
    isFavorite = false,
    onFavoriteToggle,
    isSelected = false,
    onSelectToggle,
}) => {
    const [selectionRange, setSelectionRange] = useState<[number, number] | null>(null);
    const [isHovering, setIsHovering] = useState(false);
    const [isMenuClicked, setIsMenuClicked] = useState(false);
    const inputRef = useRef<HTMLInputElement | null>(null);
    const cardRef = useRef<HTMLDivElement>(null);

    // Update when menuOpen prop changes
    useEffect(() => {
        if (menuOpen) {
            setIsMenuClicked(true);
        }
    }, [menuOpen]);

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
        setIsMenuClicked(true); // Set menu as clicked
        onMenuClick(event);
    };

    // Handle clicks outside to detect when menu should be considered closed
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            // If we click outside the card and the menu is open, consider it closed
            if (cardRef.current && !cardRef.current.contains(event.target as Node)) {
                // This is a click outside the card
                // We'll keep the menu clicked state for a short time to allow the menu to close gracefully
                setTimeout(() => {
                    setIsMenuClicked(false);
                }, 300);
            }
        };

        // Add event listener for clicks
        document.addEventListener('mousedown', handleClickOutside);
        
        // Cleanup
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    useEffect(() => {
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

    useEffect(() => {
        if (isEditing && inputRef.current && selectionRange) {
            // After the new value is in place, reset selection
            inputRef.current.setSelectionRange(selectionRange[0], selectionRange[1]);
        }
    }, [isEditing, editedName, selectionRange]);

    // Determine if buttons should be visible
    const shouldShowButtons = isHovering || isMenuClicked;

    return (
        <Box
            ref={cardRef}
            sx={{
                position: 'relative',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                    transform: 'translateY(-4px)',
                },
            }}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
        >
            <Box
                sx={{
                    borderRadius: 4, // Increased from 2 to 4 for more curved corners
                    overflow: 'hidden',
                    bgcolor: 'background.paper',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    position: 'relative', // Ensure this is a positioning context
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

                {/* Position checkbox and favorite buttons at the top left of the card - only visible on hover */}
                <Box
                    sx={{
                        position: 'absolute',
                        top: 8,
                        left: 8,
                        display: 'flex',
                        gap: 1,
                        zIndex: 1000, // Keep high z-index to ensure it's above other elements
                        opacity: shouldShowButtons ? 1 : 0, // Only visible when hovering
                        transition: 'opacity 0.2s ease-in-out',
                        pointerEvents: shouldShowButtons ? 'auto' : 'none', // Ensure buttons are clickable only when visible
                        '&:hover': {
                            opacity: shouldShowButtons ? 1 : 0,
                        }
                    }}
                    onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
                >
                    {/* Checkbox for bulk selection */}
                    <Box
                        sx={(theme) => ({
                            bgcolor: isSelected 
                                ? alpha(theme.palette.primary.main, 0.25) // More visible background color when selected
                                : alpha(theme.palette.background.paper, 0.7),
                            borderRadius: '50%',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            padding: '4px',
                            border: isSelected 
                                ? `2px solid ${theme.palette.primary.main}` // Thicker border when selected
                                : 'none',
                            boxShadow: isSelected 
                                ? `0 0 0 2px ${alpha(theme.palette.primary.main, 0.5)}` // Add glow effect
                                : 'none',
                            '&:hover': {
                                bgcolor: isSelected
                                    ? alpha(theme.palette.primary.main, 0.35)
                                    : alpha(theme.palette.background.default, 0.9),
                            },
                            transition: 'all 0.2s ease-in-out',
                            transform: isSelected ? 'scale(1.15)' : 'scale(1)', // Slightly larger when selected
                        })}
                        onClick={(e) => {
                            e.stopPropagation();
                            if (onSelectToggle) {
                                onSelectToggle(id, e);
                            }
                        }}
                    >
                        <Checkbox
                            size="small"
                            checked={isSelected}
                            disableRipple
                            sx={{
                                padding: 0,
                                color: isSelected ? 'primary.main' : 'text.secondary', 
                                '&.Mui-checked': {
                                    color: 'primary.main',
                                },
                                '& .MuiSvgIcon-root': {
                                    fontSize: '1.2rem',
                                    // Apply a more visible checkmark when selected
                                    fontWeight: isSelected ? 'bold' : 'normal',
                                    filter: isSelected ? 'drop-shadow(0px 0px 1px rgba(0,0,0,0.5))' : 'none',
                                }
                            }}
                        />
                    </Box>
                    
                    {/* Favorite button */}
                    <IconButton
                        size="small"
                        onClick={(e) => {
                            e.stopPropagation();
                            if (onFavoriteToggle) {
                                onFavoriteToggle(e);
                            }
                        }}
                        sx={(theme) => ({
                            bgcolor: alpha(theme.palette.background.paper, 0.7),
                            padding: '4px',
                            '&:hover': {
                                bgcolor: alpha(theme.palette.background.default, 0.9),
                            }
                        })}
                    >
                        {isFavorite ? (
                            <FavoriteIcon fontSize="small" color="error" />
                        ) : (
                            <FavoriteBorderIcon fontSize="small" />
                        )}
                    </IconButton>
                </Box>

                {/* Position buttons at the top right of the card, visible on hover or when menu is open */}
                <Box
                    sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        display: 'flex',
                        gap: 1,
                        zIndex: 10, // Increased z-index to ensure buttons are above other elements
                        opacity: shouldShowButtons ? 1 : 0, // Visible when hovering or menu is clicked
                        transition: 'opacity 0.2s ease-in-out',
                        pointerEvents: shouldShowButtons ? 'auto' : 'none', // Ensure buttons are clickable when visible
                    }}
                    onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
                >
                    <IconButton
                        size="small"
                        onClick={handleDeleteClick}
                        sx={(theme) => ({
                            bgcolor: alpha(theme.palette.background.paper, 0.7),
                            padding: '4px',
                            '&:hover': {
                                bgcolor: alpha(theme.palette.background.default, 0.9),
                            }
                        })}
                    >
                        <DeleteIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={handleMenuClick}
                        sx={(theme) => ({
                            bgcolor: alpha(theme.palette.background.paper, 0.7),
                            padding: '4px',
                            '&:hover': {
                                bgcolor: alpha(theme.palette.background.default, 0.9),
                            }
                        })}
                    >
                        <MoreVertIcon fontSize="small" />
                    </IconButton>
                </Box>

                {/* Metadata section */}
                {showMetadata && (
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
                                                        multiline
                                                        sx={{ 
                                                            width: '100%',
                                                            '& .MuiInputBase-root': {
                                                                width: '100%',
                                                                minHeight: '2.5em',
                                                                height: 'auto',
                                                            },
                                                            '& .MuiInputBase-input': {
                                                                whiteSpace: 'normal',
                                                                wordBreak: 'break-word',
                                                                overflow: 'visible',
                                                                textOverflow: 'clip',
                                                                width: '100%',
                                                                minHeight: '1.5em',
                                                                height: 'auto',
                                                                lineHeight: '1.5',
                                                            }
                                                        }}
                                                        InputProps={{
                                                            endAdornment: isRenaming && (
                                                              <CircularProgress size={16} />
                                                            )
                                                          }}
                                                    />
                                                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', mt: 1 }}>
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
                                                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                                                    <Typography
                                                        sx={{
                                                            wordBreak: 'break-word',
                                                            whiteSpace: 'normal',
                                                            overflow: 'visible',
                                                            textOverflow: 'clip',
                                                            width: '100%',
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
                        </Box>
                    </Box>
                )}
            </Box>
        </Box>
    );
};

export default AssetCard;
