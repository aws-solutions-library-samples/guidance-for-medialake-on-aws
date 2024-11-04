import React, { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
    Box,
    Typography,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    CircularProgress,
    Breadcrumbs,
    Link,
    Paper,
    Divider,
    Button,
    TextField,
    IconButton,
    Menu,
    MenuItem
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useS3Explorer } from '../../api/hooks/useS3Explorer';
import { formatFileSize } from '../../common/helpers/utils';

export const S3Explorer: React.FC = () => {
    const { connectorId } = useParams<{ connectorId: string }>();
    const [currentPath, setCurrentPath] = useState<string>('');
    const [continuationToken, setContinuationToken] = useState<string | null>(null);
    const [nameFilter, setNameFilter] = useState<string>('');
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedObject, setSelectedObject] = useState<string | null>(null);

    const breadcrumbPaths = useMemo(() => {
        const paths = currentPath.split('/').filter(Boolean);
        return ['', ...paths];
    }, [currentPath]);

    const { data, isLoading, error } = useS3Explorer({
        connectorId: connectorId || '',
        prefix: currentPath,
        delimiter: '/',
        continuationToken
    });

    const handlePathClick = useCallback((path: string) => {
        setCurrentPath(path);
        setContinuationToken(null);
    }, []);

    const handleLoadMore = useCallback(() => {
        if (data?.data.nextContinuationToken) {
            setContinuationToken(data.data.nextContinuationToken);
        }
    }, [data?.data.nextContinuationToken]);

    const handleMenuClick = (event: React.MouseEvent<HTMLElement>, objectKey: string) => {
        event.stopPropagation();
        setAnchorEl(event.currentTarget);
        setSelectedObject(objectKey);
    };

    const handleMenuClose = () => {
        setAnchorEl(null);
        setSelectedObject(null);
    };

    const handleRename = () => {
        // TODO: Implement rename functionality
        console.log('Rename:', selectedObject);
        handleMenuClose();
    };

    const handleDelete = () => {
        // TODO: Implement delete functionality
        console.log('Delete:', selectedObject);
        handleMenuClose();
    };

    const filteredObjects = useMemo(() => {
        if (!data?.data.objects) return [];
        return data.data.objects.filter(obj =>
            obj.Key.toLowerCase().includes(nameFilter.toLowerCase())
        );
    }, [data?.data.objects, nameFilter]);

    const filteredPrefixes = useMemo(() => {
        if (!data?.data.commonPrefixes) return [];
        return data.data.commonPrefixes.filter(prefix =>
            prefix.toLowerCase().includes(nameFilter.toLowerCase())
        );
    }, [data?.data.commonPrefixes, nameFilter]);

    const renderFolders = () => {
        return filteredPrefixes.map((prefix) => (
            <ListItem
                key={prefix}
                onClick={() => handlePathClick(prefix)}
                sx={{
                    cursor: 'pointer',
                    '&:hover': {
                        backgroundColor: 'action.hover'
                    }
                }}
            >
                <ListItemIcon>
                    <FolderIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                    primary={prefix.split('/').slice(-2)[0]}
                    secondary="Folder"
                />
                <IconButton
                    onClick={(e) => handleMenuClick(e, prefix)}
                    size="small"
                >
                    <MoreVertIcon />
                </IconButton>
            </ListItem>
        ));
    };

    const renderFiles = () => {
        return filteredObjects.map((object) => (
            <ListItem
                key={object.Key}
                sx={{
                    '&:hover': {
                        backgroundColor: 'action.hover'
                    }
                }}
            >
                <ListItemIcon>
                    <InsertDriveFileIcon />
                </ListItemIcon>
                <ListItemText
                    primary={object.Key.split('/').pop()}
                    secondary={
                        <>
                            Size: {formatFileSize(object.Size)} •
                            Storage Class: {object.StorageClass} •
                            Modified: {new Date(object.LastModified).toLocaleString()}
                        </>
                    }
                />
                <IconButton
                    onClick={(e) => handleMenuClick(e, object.Key)}
                    size="small"
                >
                    <MoreVertIcon />
                </IconButton>
            </ListItem>
        ));
    };

    if (isLoading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Box p={3}>
                <Typography color="error">
                    Error loading S3 objects: {(error as Error).message}
                </Typography>
            </Box>
        );
    }

    return (
        <Box p={3}>
            <Typography variant="h5" gutterBottom>
                S3 Explorer
            </Typography>

            <Paper sx={{ p: 2, mb: 2 }}>
                <Breadcrumbs>
                    {breadcrumbPaths.map((path, index) => {
                        const fullPath = breadcrumbPaths
                            .slice(1, index + 1)
                            .join('/') + (index > 0 ? '/' : '');
                        return (
                            <Link
                                key={path || 'root'}
                                component="button"
                                onClick={() => handlePathClick(fullPath)}
                                color="inherit"
                                sx={{ textDecoration: 'none' }}
                            >
                                {path || 'Root'}
                            </Link>
                        );
                    })}
                </Breadcrumbs>
            </Paper>

            <Box mb={2}>
                <TextField
                    label="Filter by name"
                    variant="outlined"
                    size="small"
                    value={nameFilter}
                    onChange={(e) => setNameFilter(e.target.value)}
                    fullWidth
                />
            </Box>

            <Paper>
                <List>
                    {renderFolders()}
                    {filteredPrefixes.length && filteredObjects.length ? (
                        <Divider sx={{ my: 1 }} />
                    ) : null}
                    {renderFiles()}
                </List>
            </Paper>

            {data?.data.isTruncated && (
                <Box mt={2} display="flex" justifyContent="center">
                    <Button
                        variant="outlined"
                        color="primary"
                        onClick={handleLoadMore}
                    >
                        Load More
                    </Button>
                </Box>
            )}

            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
            >
                <MenuItem onClick={handleRename}>Rename</MenuItem>
                <MenuItem onClick={handleDelete}>Delete</MenuItem>
            </Menu>
        </Box>
    );
};
