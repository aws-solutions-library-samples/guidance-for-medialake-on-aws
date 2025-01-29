import React from 'react';
import { Box, Typography, IconButton, TextField, Button } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditIcon from '@mui/icons-material/Edit';
import VideoViewer from '../common/VideoViewer';

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
    onImageClick: () => void;
    onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
    onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
    placeholderImage?: string;
    onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
    isEditing?: boolean;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onEditNameComplete?: (save: boolean) => void;
}

const AssetCard: React.FC<AssetCardProps> = ({
    id,
    name,
    thumbnailUrl,
    proxyUrl,
    assetType,
    fields,
    renderField,
    onImageClick,
    onDeleteClick,
    onMenuClick,
    onEditClick,
    placeholderImage = 'https://placehold.co/300x200?text=Placeholder',
    onImageError,
    isEditing,
    editedName,
    onEditNameChange,
    onEditNameComplete,
}) => {
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

    return (
        <Box
            sx={{
                position: 'relative',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                    transform: 'translateY(-4px)'
                }
            }}
        >
            <Box
                onClick={onImageClick}
                sx={{
                    cursor: 'pointer',
                    borderRadius: 2,
                    overflow: 'hidden',
                    bgcolor: 'background.paper',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    '&:hover': {
                        boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
                    }
                }}
            >

                {assetType === 'Video' ? (
                    // <VideoViewer videoSrc={proxyUrl} />
                    <video
                        style={{
                            width: '100%',
                            height: 200,
                            backgroundColor: 'rgba(0,0,0,0.03)',
                            objectFit: 'contain'
                        }}
                        controls src={proxyUrl}></video>
                ) : (
                    <Box
                        component="img"
                        src={thumbnailUrl || placeholderImage}
                        alt={name}
                        onError={onImageError || defaultImageErrorHandler}
                        data-image-id={id}
                        sx={{
                            width: '100%',
                            height: 200,
                            backgroundColor: 'rgba(0,0,0,0.03)',
                            objectFit: 'contain'
                        }}
                    />
                )}
                <Box sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {fields.map(field => field.visible && (
                            <Box key={field.id}>
                                <Typography
                                    variant="caption"
                                    color="text.secondary"
                                >
                                    {field.label}:
                                </Typography>
                                {field.id === 'name' && onEditClick ? (
                                    isEditing ? (
                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                            <TextField
                                                value={editedName}
                                                onChange={onEditNameChange}
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
                                            />
                                            <Box sx={{ display: 'flex', gap: 1 }}>
                                                <Button
                                                    size="small"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onEditNameComplete?.(true);
                                                    }}
                                                    variant="contained"
                                                >
                                                    Save
                                                </Button>
                                                <Button
                                                    size="small"
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
                                            <Typography sx={{ wordBreak: "break-word" }} display="inline" variant="body2">
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
                                    <Typography variant="body2">
                                        {renderField(field.id)}
                                    </Typography>
                                )}
                            </Box>
                        ))}
                        <Box sx={{
                            display: 'flex',
                            justifyContent: 'flex-end',
                            gap: 1,
                            mt: 1
                        }}>
                            <IconButton
                                size="small"
                                onClick={handleDeleteClick}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                                size="small"
                                onClick={handleMenuClick}
                            >
                                <MoreVertIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    </Box>
                </Box>
            </Box>
        </Box>
    );
};

export default AssetCard;
