import React from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';

export interface AssetField {
    id: string;
    label: string;
    visible: boolean;
}

export interface AssetCardProps {
    id: string;
    name: string;
    thumbnailUrl?: string;
    fields: AssetField[];
    renderField: (fieldId: string) => string | React.ReactNode;
    onImageClick: () => void;
    onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
    placeholderImage?: string;
    onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
}

const AssetCard: React.FC<AssetCardProps> = ({
    id,
    name,
    thumbnailUrl,
    fields,
    renderField,
    onImageClick,
    onDeleteClick,
    onMenuClick,
    placeholderImage = 'https://placehold.co/300x200',
    onImageError,
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
                <Box
                    component="img"
                    src={thumbnailUrl || placeholderImage}
                    alt={name}
                    onError={onImageError || defaultImageErrorHandler}
                    data-image-id={id}
                    sx={{
                        width: '100%',
                        height: 200,
                        objectFit: 'cover',
                        backgroundColor: 'rgba(0,0,0,0.03)'
                    }}
                />
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
                                <Typography variant="body2">
                                    {renderField(field.id)}
                                </Typography>
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
