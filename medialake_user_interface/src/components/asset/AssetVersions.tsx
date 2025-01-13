import React from 'react';
import { Box, Typography, List, ListItem, ListItemIcon, ListItemText, Chip } from '@mui/material';
import HistoryIcon from '@mui/icons-material/History';
import { formatFileSize } from '../../utils/imageUtils';

interface Version {
    id: string;
    src: string;
    type: string;
    description: string;
}

interface AssetVersionsProps {
    versions: Version[];
}

const AssetVersions: React.FC<AssetVersionsProps> = ({ versions }) => {
    return (
        <Box sx={{ p: 2 }}>
            <List>
                {versions.map((version, index) => (
                    <ListItem
                        key={version.id}
                        sx={{
                            mb: 2,
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: 1,
                            flexDirection: 'column',
                            alignItems: 'flex-start',
                            p: 2
                        }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', mb: 1 }}>
                            <ListItemIcon sx={{ minWidth: 40 }}>
                                <HistoryIcon />
                            </ListItemIcon>
                            <ListItemText
                                primary={version.type}
                                secondary={version.description}
                            />
                        </Box>
                        <Box sx={{ pl: 5, width: '100%' }}>
                            <Chip
                                label={`v${versions.length - index}.0`}
                                size="small"
                                sx={{ mr: 1 }}
                            />
                        </Box>
                    </ListItem>
                ))}
            </List>
        </Box>
    );
};

export default AssetVersions;
