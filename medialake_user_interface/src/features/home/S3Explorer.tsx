import React, { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
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
    MenuItem,
    useTheme,
    alpha,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useS3Explorer } from '../../api/hooks/useS3Explorer';
import { formatFileSize } from '../../common/helpers/utils';

interface S3ExplorerProps {
    connectorId: string;
}

export const S3Explorer: React.FC<S3ExplorerProps> = ({ connectorId }) => {
    const { t } = useTranslation();
    const theme = useTheme();
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
        connectorId,
        prefix: currentPath,
        delimiter: '/',
        continuationToken
    });

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

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
                    borderRadius: '8px',
                    my: 0.5,
                    '&:hover': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.02),
                    },
                    transition: 'background-color 0.2s ease',
                }}
            >
                <ListItemIcon>
                    <FolderIcon sx={{ color: theme.palette.primary.main }} />
                </ListItemIcon>
                <ListItemText
                    primary={
                        <Typography variant="body2" sx={{ fontWeight: 500, color: theme.palette.primary.main }}>
                            {prefix.split('/').slice(-2)[0]}
                        </Typography>
                    }
                    secondary={
                        <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                            {t('common.folder')}
                        </Typography>
                    }
                />
                <IconButton
                    onClick={(e) => handleMenuClick(e, prefix)}
                    size="small"
                    sx={{
                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.2),
                        },
                    }}
                >
                    <MoreVertIcon fontSize="small" />
                </IconButton>
            </ListItem>
        ));
    };

    const renderFiles = () => {
        return filteredObjects.map((object) => (
            <ListItem
                key={object.Key}
                sx={{
                    borderRadius: '8px',
                    my: 0.5,
                    '&:hover': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.02),
                    },
                    transition: 'background-color 0.2s ease',
                }}
            >
                <ListItemIcon>
                    <InsertDriveFileIcon sx={{ color: theme.palette.text.secondary }} />
                </ListItemIcon>
                <ListItemText
                    primary={
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {object.Key.split('/').pop()}
                        </Typography>
                    }
                    secondary={
                        <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                            {t('s3Explorer.file.info', {
                                size: formatFileSize(object.Size),
                                storageClass: object.StorageClass,
                                modified: formatDate(object.LastModified)
                            })}
                        </Typography>
                    }
                />
                <IconButton
                    onClick={(e) => handleMenuClick(e, object.Key)}
                    size="small"
                    sx={{
                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.2),
                        },
                    }}
                >
                    <MoreVertIcon fontSize="small" />
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
                    {t('s3Explorer.error.loading', { message: (error as Error).message })}
                </Typography>
            </Box>
        );
    }

    return (
        <Box p={3}>
            <Box mb={2}>
                <TextField
                    label={t('s3Explorer.filter.label')}
                    variant="outlined"
                    size="small"
                    value={nameFilter}
                    onChange={(e) => setNameFilter(e.target.value)}
                    fullWidth
                    sx={{
                        '& .MuiOutlinedInput-root': {
                            borderRadius: '8px',
                            backgroundColor: theme.palette.background.paper,
                        }
                    }}
                />
            </Box>

            <Paper elevation={0} sx={{
                p: 2,
                mb: 2,
                borderRadius: '12px',
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            }}>
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
                                sx={{
                                    textDecoration: 'none',
                                    color: theme.palette.primary.main,
                                    '&:hover': {
                                        textDecoration: 'underline',
                                    },
                                }}
                            >
                                {path || t('common.root')}
                            </Link>
                        );
                    })}
                </Breadcrumbs>
            </Paper>

            <Paper elevation={0} sx={{
                borderRadius: '12px',
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                backgroundColor: theme.palette.background.paper,
            }}>
                <List sx={{ p: 1 }}>
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
                        variant="contained"
                        onClick={handleLoadMore}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            backgroundColor: theme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.dark,
                            },
                        }}
                    >
                        {t('common.loadMore')}
                    </Button>
                </Box>
            )}

            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        borderRadius: '8px',
                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        backgroundColor: theme.palette.background.paper,
                        overflow: 'visible',
                        mt: 1,
                    },
                }}
            >
                <MenuItem
                    onClick={handleRename}
                    sx={{
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        },
                    }}
                >
                    {t('s3Explorer.menu.rename')}
                </MenuItem>
                <MenuItem
                    onClick={handleDelete}
                    sx={{
                        color: theme.palette.error.main,
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.error.main, 0.1),
                        },
                    }}
                >
                    {t('s3Explorer.menu.delete')}
                </MenuItem>
            </Menu>
        </Box>
    );
};
