import React from 'react';
import { Box, Paper } from '@mui/material';
import { ImageViewer } from '../common/ImageViewer';

interface AssetImageProps {
    src: string;
    alt?: string;
}

const AssetImage: React.FC<AssetImageProps> = ({ src, alt }) => {
    return (
        <Box
            sx={{
                position: 'sticky',
                top: 120, // Below breadcrumb and header
                zIndex: 900,
                mb: 3,
                height: 'calc(50vh - 120px)', // Take half viewport height minus top offset
                minHeight: 300, // Minimum height
                maxHeight: 600, // Maximum height
            }}
        >
            <Paper
                elevation={1}
                sx={{
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                    bgcolor: 'background.paper',
                    '& img': {
                        maxWidth: '100%',
                        maxHeight: '100%',
                        objectFit: 'contain'
                    }
                }}
            >
                <ImageViewer
                    imageSrc={src}
                    maxHeight="100%"
                    filename={alt || 'asset_preview'}
                />
            </Paper>
        </Box>
    );
};

export default AssetImage;
