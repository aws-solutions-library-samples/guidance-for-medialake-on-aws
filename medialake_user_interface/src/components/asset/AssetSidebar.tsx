import React, { useState } from 'react';
import {
    Box,
    Typography,
    Tabs,
    Tab,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Divider,
    Button,
    IconButton,
    Badge,
    Avatar,
    TextField,
    Paper,
    alpha,
    useTheme,
    Tooltip
} from '@mui/material';
import { RightSidebar } from '../common/RightSidebar';

// Icons
import HistoryIcon from '@mui/icons-material/History';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import GroupsIcon from '@mui/icons-material/Groups';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TimelineIcon from '@mui/icons-material/Timeline';
import SendIcon from '@mui/icons-material/Send';
import PersonIcon from '@mui/icons-material/Person';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import ImageIcon from '@mui/icons-material/Image';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import MovieIcon from '@mui/icons-material/Movie';
import DownloadIcon from '@mui/icons-material/Download';
import PreviewIcon from '@mui/icons-material/Preview';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { RefObject } from 'react';
import { VideoViewer, VideoViewerRef, Marker } from '../common/VideoViewer';


interface MarkerInfo {
    id: number;
    timeObservation: {
        start: number;
        end: number;
    };
    style: {
        color: string;
    };
}

interface AssetSidebarProps {
    versions?: any[];
    comments?: any[];
    onAddComment?: (comment: string) => void;
    videoViewerRef?: RefObject<VideoViewerRef>;
}



interface AssetVersionProps {
    versions: any[];
}

interface AssetMarkersProps {
    onMarkerAdd?: () => void; 
    videoViewerRef?: RefObject<VideoViewerRef>; // Add this
}

interface AssetCollaborationProps {
    comments?: any[];
    onAddComment?: (comment: string) => void;
}

interface AssetPipelinesProps {}

interface AssetActivityProps {}

// Version content component (using existing data)
const AssetVersions: React.FC<AssetVersionProps> = ({ versions = [] }) => {
    const theme = useTheme();
    
    const getVersionIcon = (version: any) => {
        const type = version.type.toLowerCase();
        
        if (type === 'original') {
            return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
        } else if (type === 'proxy' || type.includes('proxy')) {
            return <PlayCircleOutlineIcon fontSize="small" color="secondary" sx={{ mr: 1 }} />;
        } else if (type === 'thumbnail' || type.includes('thumb')) {
            return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
        } else if (type === 'pdf' || version.format?.toLowerCase()?.includes('pdf')) {
            return <PictureAsPdfIcon fontSize="small" color="error" sx={{ mr: 1 }} />;
        }
        
        // Default icon based on format
        if (version.format?.toLowerCase()?.includes('video') || 
            version.format?.toLowerCase()?.includes('mp4')) {
            return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
        } else if (version.format?.toLowerCase()?.includes('image') || 
                  version.format?.toLowerCase()?.includes('jpg') || 
                  version.format?.toLowerCase()?.includes('png')) {
            return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
        }
        
        return <InfoOutlinedIcon fontSize="small" color="action" sx={{ mr: 1 }} />;
    };

    return (
        <List disablePadding sx={{ p: 1 }}>
            {versions.length === 0 ? (
                <Box sx={{ 
                    p: 3, 
                    textAlign: 'center',
                    bgcolor: alpha(theme.palette.background.paper, 0.4),
                    borderRadius: 1
                }}>
                    <Typography variant="body2" color="text.secondary">
                        No versions available
                    </Typography>
                </Box>
            ) : (
                versions.map((version, index) => (
                    <React.Fragment key={version.id}>
                        <ListItem 
                            alignItems="flex-start" 
                            sx={{ 
                                py: 2,
                                px: 1,
                                borderRadius: 1,
                                '&:hover': {
                                    bgcolor: alpha(theme.palette.primary.main, 0.04)
                                }
                            }}
                        >
                            <Box sx={{ width: '100%' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                    {getVersionIcon(version)}
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                        {version.type}
                                    </Typography>
                                    <Typography 
                                        variant="caption" 
                                        color="text.secondary"
                                        sx={{ ml: 'auto' }}
                                    >
                                        {version.format}
                                    </Typography>
                                </Box>
                                <Typography variant="body2" color="text.secondary">
                                    {version.description}
                                </Typography>
                                <Box sx={{ display: 'flex', mt: 1 }}>
                                    <Tooltip title="Download this version">
                                        <Button 
                                            variant="outlined" 
                                            size="small" 
                                            sx={{ mr: 1, textTransform: 'none' }}
                                            href={version.src}
                                            target="_blank"
                                            startIcon={<DownloadIcon fontSize="small" />}
                                        >
                                            Download
                                        </Button>
                                    </Tooltip>
                                    <Tooltip title="Preview this version">
                                        <Button 
                                            variant="text" 
                                            size="small" 
                                            sx={{ textTransform: 'none' }}
                                            startIcon={<PreviewIcon fontSize="small" />}
                                        >
                                            Preview
                                        </Button>
                                    </Tooltip>
                                </Box>
                            </Box>
                        </ListItem>
                        {index < versions.length - 1 && <Divider component="li" sx={{ my: 0.5 }} />}
                    </React.Fragment>
                ))
            )}
        </List>
    );
};


// Markers content component
const AssetMarkers: React.FC<AssetMarkersProps> = ({videoViewerRef}) => {
    const theme = useTheme();
    const [markers, setMarkers] = useState<MarkerInfo[]>([]); // Add this state

    // const addMakerDiv = (time: number, markers,setMarkers) =>{
    //     setMarkers(prev => [...prev, `Marker: ${prev.length + 1}
    //         'Marker time : ${time}'`]);
    //     console.log("time: ",time);
    //     console.log("Acao 5: Marker adicionado")
    // }

    // Add this function
    const addMarker = () => {
        const marker = videoViewerRef.current.hello();
        setMarkers(prev => [...prev, {
            id: prev.length + 1,
            timeObservation: {
                start: marker.timeObservation.start,
                end: marker.timeObservation.end
            },
            style: {
                color: marker.style.color
            }
        }]);
        
    };

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Add time markers to highlight important moments in your media.
            </Typography>
            
            <Tooltip title="Create a new time marker">
                <Button 
                    variant="contained" 
                    fullWidth 
                    sx={{ mt: 1 }}
                    startIcon={<BookmarkIcon />}
                    onClick = {addMarker}
                >
                    Add Marker
                </Button>
            </Tooltip>
           {/* Add this section to render markers */}
           {markers.map((marker, index) => (
                <Box
                    key={index}
                    sx={{
                        mt: 2,
                        p: 2,
                        bgcolor: alpha(marker.style.color, 0.1),
                        borderRadius: 1,
                        border: `1px solid ${alpha(marker.style.color, 0.2)}`,
                    }}
                >
                    <Typography variant="body2" component="div">
                        <Box>
                            <Typography variant="body2">
                                <b>Marker:</b> {marker.id}
                            </Typography>
                            <Typography variant="body2">
                                <b>IN:</b> {marker.timeObservation.start}
                            </Typography>
                            <Typography variant="body2">
                                <b>OUT: </b> {marker.timeObservation.end}
                            </Typography>
                        </Box>
                    </Typography>
                </Box>
            ))}

        </Box>
    );
};

// Collaboration content component
const AssetCollaboration: React.FC<AssetCollaborationProps> = ({ comments = [], onAddComment }) => {
    const [newComment, setNewComment] = useState('');
    const theme = useTheme();
    
    const handleSubmitComment = () => {
        if (newComment.trim() && onAddComment) {
            onAddComment(newComment);
            setNewComment('');
        }
    };
    
    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
                {comments.length === 0 ? (
                    <Paper 
                        variant="outlined" 
                        sx={{ 
                            p: 3, 
                            textAlign: 'center',
                            bgcolor: alpha(theme.palette.background.paper, 0.4)
                        }}
                    >
                        <GroupsIcon color="disabled" sx={{ fontSize: 40, mb: 1, opacity: 0.7 }} />
                        <Typography color="text.secondary" sx={{ mb: 1 }}>
                            No comments yet
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Start the conversation by adding a comment below.
                        </Typography>
                    </Paper>
                ) : (
                    <List disablePadding>
                        {comments.map((comment, index) => (
                            <ListItem 
                                key={index} 
                                alignItems="flex-start" 
                                sx={{ 
                                    px: 1, 
                                    py: 1.5,
                                    borderRadius: 1,
                                    mb: 1,
                                    bgcolor: index % 2 === 0 ? 'transparent' : alpha(theme.palette.background.paper, 0.4)
                                }}
                            >
                                <ListItemIcon sx={{ minWidth: 40 }}>
                                    <Avatar 
                                        src={comment.avatar} 
                                        alt={comment.user}
                                        sx={{ width: 32, height: 32 }}
                                    >
                                        {comment.user.charAt(0)}
                                    </Avatar>
                                </ListItemIcon>
                                <ListItemText
                                    primary={
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <Typography variant="subtitle2" component="span">
                                                {comment.user}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {comment.timestamp}
                                            </Typography>
                                        </Box>
                                    }
                                    secondary={
                                        <Typography 
                                            variant="body2" 
                                            color="text.primary"
                                            sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}
                                        >
                                            {comment.content}
                                        </Typography>
                                    }
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Box>
            
            <Divider />
            
            <Box sx={{ p: 2, bgcolor: alpha(theme.palette.background.paper, 0.3) }}>
                <TextField
                    variant="outlined"
                    size="small"
                    fullWidth
                    multiline
                    rows={2}
                    placeholder="Add a comment..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    sx={{ 
                        mb: 1,
                        '& .MuiOutlinedInput-root': {
                            backgroundColor: theme.palette.background.paper
                        }
                    }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Tooltip title="Post your comment">
                        <span>
                            <Button 
                                variant="contained" 
                                size="small" 
                                endIcon={<SendIcon />}
                                disabled={!newComment.trim()}
                                onClick={handleSubmitComment}
                            >
                                Post
                            </Button>
                        </span>
                    </Tooltip>
                </Box>
            </Box>
        </Box>
    );
};

// Pipelines content component
const AssetPipelines: React.FC<AssetPipelinesProps> = () => {
    const theme = useTheme();
    
    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Run processing pipelines on this asset to transform or analyze it.
            </Typography>
            
            <Paper 
                variant="outlined" 
                sx={{ 
                    p: 2, 
                    mb: 2,
                    borderColor: alpha(theme.palette.info.main, 0.2),
                    transition: 'all 0.2s ease',
                    '&:hover': {
                        borderColor: theme.palette.info.main,
                        boxShadow: `0 4px 8px ${alpha(theme.palette.info.main, 0.15)}`
                    }
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <AccountTreeIcon color="info" fontSize="small" sx={{ mr: 1 }} />
                    <Typography variant="subtitle2">Thumbnail Generation</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Creates multiple thumbnail images at different resolutions.
                </Typography>
                <Tooltip title="Run this pipeline on the current asset">
                    <Button variant="outlined" size="small" color="info">
                        Run Pipeline
                    </Button>
                </Tooltip>
            </Paper>
            
            <Paper 
                variant="outlined" 
                sx={{ 
                    p: 2, 
                    mb: 2,
                    borderColor: alpha(theme.palette.warning.main, 0.2),
                    transition: 'all 0.2s ease',
                    '&:hover': {
                        borderColor: theme.palette.warning.main,
                        boxShadow: `0 4px 8px ${alpha(theme.palette.warning.main, 0.15)}`
                    }
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <AccountTreeIcon color="warning" fontSize="small" sx={{ mr: 1 }} />
                    <Typography variant="subtitle2">AI Analysis</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Extracts metadata, tags, and insights using machine learning.
                </Typography>
                <Tooltip title="Run this pipeline on the current asset">
                    <Button variant="outlined" size="small" color="warning">
                        Run Pipeline
                    </Button>
                </Tooltip>
            </Paper>
            
            <Tooltip title="Browse all available pipelines">
                <Button variant="text" fullWidth sx={{ mt: 2 }}>
                    View All Pipelines
                </Button>
            </Tooltip>
        </Box>
    );
};

// Activity content component
const AssetActivity: React.FC<AssetActivityProps> = () => {
    const theme = useTheme();
    const activities = [
        { user: 'System', action: 'Created asset', timestamp: '2023-11-15 09:30:22', icon: <PersonIcon color="primary" /> },
        { user: 'John Doe', action: 'Added to collection', timestamp: '2023-11-15 10:15:43', icon: <PersonIcon color="primary" /> },
        { user: 'AI Pipeline', action: 'Generated metadata', timestamp: '2023-11-15 11:22:17', icon: <TimelineIcon color="secondary" /> },
        { user: 'Jane Smith', action: 'Added comment', timestamp: '2023-11-15 14:05:36', icon: <PersonIcon color="primary" /> },
    ];
    
    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Recent activity history for this asset.
            </Typography>
            
            <List 
                disablePadding
                sx={{
                    bgcolor: alpha(theme.palette.background.paper, 0.4),
                    borderRadius: 1,
                    p: 1,
                }}
            >
                {activities.map((activity, index) => (
                    <React.Fragment key={index}>
                        <ListItem 
                            alignItems="flex-start" 
                            sx={{ 
                                px: 1,
                                py: 1.5,
                                borderRadius: 1,
                                '&:hover': {
                                    bgcolor: alpha(theme.palette.background.paper, 0.6)
                                }
                            }}
                        >
                            <ListItemIcon sx={{ minWidth: 36 }}>
                                {activity.icon}
                            </ListItemIcon>
                            <ListItemText
                                primary={activity.action}
                                secondary={
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                        <Typography variant="caption" component="span">
                                            {activity.user}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" component="span">
                                            {activity.timestamp}
                                        </Typography>
                                    </Box>
                                }
                            />
                        </ListItem>
                        {index < activities.length - 1 && <Divider component="li" sx={{ my: 0.5 }} />}
                    </React.Fragment>
                ))}
            </List>
            
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                <Tooltip title="Load more activities">
                    <Button size="small" color="primary">
                        Load More
                    </Button>
                </Tooltip>
            </Box>
        </Box>
    );
};
export const AssetSidebar: React.FC<AssetSidebarProps> = ({ videoViewerRef,versions = [],comments = [],onAddComment }) => {
    const [currentTab, setCurrentTab] = useState(0);
    const theme = useTheme();

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    return (
        <RightSidebar>
            <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                {/* Tabs navigation - now with fixed height and no scroll */}
                <Box sx={{ 
                    borderBottom: 1, 
                    borderColor: 'divider',
                    bgcolor: alpha(theme.palette.background.default, 0.4)
                }}>
                    <Tabs 
                        value={currentTab} 
                        onChange={handleTabChange}
                        variant="fullWidth"
                        aria-label="asset sidebar tabs"
                        sx={{
                            minHeight: 40,
                            '& .MuiTab-root': {
                                minHeight: 40,
                                textTransform: 'none',
                                fontSize: '0.75rem',
                                fontWeight: 500,
                                opacity: 0.7,
                                transition: 'all 0.2s',
                                padding: '6px 8px',
                                minWidth: 'auto',
                                '&.Mui-selected': {
                                    opacity: 1,
                                    fontWeight: 600,
                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                }
                            },
                            '& .MuiTabs-indicator': {
                                height: 2,
                                borderTopLeftRadius: 2,
                                borderTopRightRadius: 2,
                            }
                        }}
                    >
                        <Tab 
                            icon={<BookmarkIcon fontSize="small" />} 
                            label="Markers" 
                            id="sidebar-tab-0"
                            aria-controls="sidebar-tabpanel-0"
                            iconPosition="start"
                        />
                        <Tab 
                            icon={<HistoryIcon fontSize="small" />} 
                            label={
                                <Badge 
                                    badgeContent={versions.length} 
                                    color="primary" 
                                    sx={{ 
                                        pr: 1,
                                        '& .MuiBadge-badge': {
                                            fontSize: '0.65rem',
                                            height: 16,
                                            minWidth: 16,
                                            padding: '0 4px'
                                        }
                                    }}
                                >
                                    <span>Versions</span>
                                </Badge>
                            }
                            id="sidebar-tab-1"
                            aria-controls="sidebar-tabpanel-1"
                            iconPosition="start"
                        />
                    </Tabs>
                </Box>
                
                {/* Tab content */}
                <Box sx={{ flex: 1, overflow: 'hidden' }}>
                    <Box
                        role="tabpanel"
                        hidden={currentTab !== 0}
                        id="sidebar-tabpanel-0"
                        aria-labelledby="sidebar-tab-0"
                        sx={{ height: '100%', overflow: 'auto' }}
                    >
                                        {currentTab === 0 && (
                    <AssetMarkers 
                        videoViewerRef= {videoViewerRef}
                        
                    />
                )}
                    </Box>
                    
                    <Box
                        role="tabpanel"
                        hidden={currentTab !== 1}
                        id="sidebar-tabpanel-1"
                        aria-labelledby="sidebar-tab-1"
                        sx={{ height: '100%', overflow: 'auto' }}
                    >
                        {currentTab === 1 && <AssetVersions versions={versions} />}
                    </Box>
                </Box>
            </Box>
        </RightSidebar>
    );
};

export default AssetSidebar;
