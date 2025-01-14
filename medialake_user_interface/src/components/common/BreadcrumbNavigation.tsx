import React, { useState } from 'react';
import { Box, Typography, IconButton, Menu, MenuItem, Divider } from '@mui/material';
import { ChevronLeft, ChevronRight, History, Trash2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useRecentlyViewed } from '../../contexts/RecentlyViewedContext';
import { formatDistanceToNow } from 'date-fns';

interface BreadcrumbNavigationProps {
    searchTerm: string;
    currentResult: number;
    totalResults: number;
    onBack: () => void;
    onPrevious: () => void;
    onNext: () => void;
}

const BreadcrumbNavigation: React.FC<BreadcrumbNavigationProps> = ({
    searchTerm,
    currentResult,
    totalResults,
    onBack,
    onPrevious,
    onNext,
}) => {
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);
    const navigate = useNavigate();
    const { items, clearAll } = useRecentlyViewed();

    const handleHistoryClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleHistoryClose = () => {
        setAnchorEl(null);
    };

    return (
        <Box
            sx={{
                position: 'sticky',
                top: 64, // Below main header
                zIndex: 1100,
                bgcolor: 'common.white',
                borderBottom: 1,
                borderColor: 'grey.100',
                px: 3,
                py: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}
        >
            {/* Left Section */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Link
                    to="/search"
                    style={{
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        color: 'rgb(37, 99, 235)', // text-blue-600
                        fontSize: '0.875rem', // text-sm
                    }}
                    onClick={(e) => {
                        e.preventDefault();
                        onBack();
                    }}
                >
                    <ChevronLeft size={16} />
                    <Typography
                        sx={{
                            fontSize: 'inherit',
                            '&:hover': { textDecoration: 'underline' }
                        }}
                    >
                        Back to search
                    </Typography>
                </Link>

                <Typography
                    sx={{
                        fontSize: '0.875rem',
                        color: 'text.secondary',
                        display: 'flex',
                        alignItems: 'center',
                        '&::before': {
                            content: '"/"',
                            mx: 1,
                            color: 'grey.400'
                        }
                    }}
                >
                    Search: "{searchTerm}"
                </Typography>

            </Box>

            {/* Right Section */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <IconButton
                    onClick={onPrevious}
                    size="small"
                    sx={{ color: 'rgb(37, 99, 235)' }}
                >
                    <ChevronLeft size={16} />
                </IconButton>
                <IconButton
                    onClick={onNext}
                    size="small"
                    sx={{ color: 'rgb(37, 99, 235)' }}
                >
                    <ChevronRight size={16} />
                </IconButton>
                <IconButton
                    onClick={handleHistoryClick}
                    size="small"
                    sx={{ color: 'rgb(37, 99, 235)' }}
                >
                    <History size={16} />
                </IconButton>

                <Menu
                    anchorEl={anchorEl}
                    open={open}
                    onClose={handleHistoryClose}
                    anchorOrigin={{
                        vertical: 'bottom',
                        horizontal: 'right',
                    }}
                    transformOrigin={{
                        vertical: 'top',
                        horizontal: 'right',
                    }}
                    PaperProps={{
                        sx: { minWidth: 280 }
                    }}
                >
                    <Box sx={{
                        px: 2,
                        py: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                    }}>
                        <Typography variant="subtitle2" sx={{ color: 'text.secondary' }}>
                            Recently Viewed
                        </Typography>
                        <IconButton
                            size="small"
                            onClick={clearAll}
                            sx={{ color: 'text.secondary' }}
                        >
                            <Trash2 size={16} />
                        </IconButton>
                    </Box>
                    <Divider />
                    {items.length === 0 ? (
                        <Box sx={{ p: 2 }}>
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                No recently viewed items
                            </Typography>
                        </Box>
                    ) : (
                        items.map((item) => (
                            <MenuItem
                                key={item.id}
                                onClick={() => {
                                    handleHistoryClose();
                                    navigate(item.path);
                                }}
                                sx={{
                                    py: 1,
                                    px: 2,
                                }}
                            >
                                <Box sx={{ width: '100%' }}>
                                    <Box sx={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'flex-start',
                                        mb: 0.5
                                    }}>
                                        <Typography sx={{
                                            fontSize: '0.875rem',
                                            fontWeight: 500,
                                            maxWidth: '80%'
                                        }}>
                                            {item.title}
                                        </Typography>
                                        <Typography
                                            variant="caption"
                                            sx={{ color: 'text.secondary' }}
                                        >
                                            {formatDistanceToNow(item.timestamp, { addSuffix: true })}
                                        </Typography>
                                    </Box>
                                    <Box sx={{
                                        display: 'flex',
                                        gap: 2,
                                        alignItems: 'center'
                                    }}>
                                        {item.metadata.duration && (
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                                {item.metadata.duration}
                                            </Typography>
                                        )}
                                        {item.metadata.dimensions && (
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                                {item.metadata.dimensions}
                                            </Typography>
                                        )}
                                        {item.metadata.fileSize && (
                                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                                {item.metadata.fileSize}
                                            </Typography>
                                        )}
                                    </Box>
                                </Box>
                            </MenuItem>
                        ))
                    )}
                </Menu>
            </Box>
        </Box>
    );
};

export default BreadcrumbNavigation;
