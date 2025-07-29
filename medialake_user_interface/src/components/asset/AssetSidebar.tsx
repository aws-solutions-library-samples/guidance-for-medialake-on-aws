import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useGeneratePresignedUrl } from "../../api/hooks/usePresignedUrl";
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
  Tooltip,
  CircularProgress,
} from "@mui/material";
import { RightSidebar } from "../common/RightSidebar";

// Icons
import HistoryIcon from "@mui/icons-material/History";
import BookmarkIcon from "@mui/icons-material/Bookmark";
import GroupsIcon from "@mui/icons-material/Groups";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import TimelineIcon from "@mui/icons-material/Timeline";
import SendIcon from "@mui/icons-material/Send";
import PersonIcon from "@mui/icons-material/Person";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import ImageIcon from "@mui/icons-material/Image";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import MovieIcon from "@mui/icons-material/Movie";
import DownloadIcon from "@mui/icons-material/Download";
import PreviewIcon from "@mui/icons-material/Preview";
import SettingsIcon from "@mui/icons-material/Settings";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import CloseIcon from "@mui/icons-material/Close";
import { RefObject } from "react";
import { VideoViewer, VideoViewerRef, Marker } from "../common/VideoViewer";
import { randomHexColor } from "../common/utils";
import {
  SCRUBBER_LANE_STYLE_DARK,
  TIMELINE_STYLE_DARK,
  PERIOD_MARKER_STYLE,
} from "../common/OmakaseTimeLineConstants";
import {
  MarkerLane,
  OmakasePlayer,
  PeriodMarker,
} from "@byomakase/omakase-player";
import { subscribe } from "diagnostics_channel";

interface MarkerInfo {
  id: string;
  name?: string;
  timeObservation: {
    start: number;
    end: number;
  };
  style: {
    color: string;
  };
  score?: number; // Optional score property for markers created from clips
}

interface AssetSidebarProps {
  versions?: any[];
  comments?: any[];
  onAddComment?: (comment: string) => void;
  videoViewerRef?: RefObject<VideoViewerRef>;
  assetId?: string;
  asset?: any;
  assetType?: string;
  searchTerm?: string; // Add searchTerm prop
}

interface AssetVersionProps {
  versions: any[];
}

interface AssetMarkersProps {
  onMarkerAdd?: () => void;
  videoViewerRef?: RefObject<VideoViewerRef>; // Add this
  markers?: MarkerInfo[];
  setMarkers?: React.Dispatch<React.SetStateAction<MarkerInfo[]>>;
  asset: any;
  assetType: string;
  searchTerm?: string; // Add searchTerm prop
  clipsMarkersCreated: boolean;
  setClipsMarkersCreated: (created: boolean) => void;
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
  const generatePresignedUrl = useGeneratePresignedUrl();
  const [downloadingVersionId, setDownloadingVersionId] = useState<
    string | null
  >(null);

  const handleDownload = async (version: any) => {
    try {
      setDownloadingVersionId(version.id);

      // Always generate a presigned URL
      // Determine the purpose based on version type
      const purpose = version.type.toLowerCase();

      const result = await generatePresignedUrl.mutateAsync({
        inventoryId: version.inventoryId || version.assetId,
        expirationTime: 60, // 1 minute in seconds
        purpose: purpose, // Pass the purpose to get the correct representation
      });

      // Create a temporary link element
      const link = document.createElement("a");
      link.href = result.presigned_url;

      // Use version name or extract filename from the URL
      const fileName =
        version.name || (version.src ? version.src.split("/").pop() : purpose);
      link.setAttribute("download", fileName);

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error("Error downloading file:", error);
    } finally {
      setDownloadingVersionId(null);
    }
  };

  const getVersionIcon = (version: any) => {
    const type = version.type.toLowerCase();

    if (type === "original") {
      return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
    } else if (type === "proxy" || type.includes("proxy")) {
      return (
        <PlayCircleOutlineIcon
          fontSize="small"
          color="secondary"
          sx={{ mr: 1 }}
        />
      );
    } else if (type === "thumbnail" || type.includes("thumb")) {
      return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
    } else if (
      type === "pdf" ||
      version.format?.toLowerCase()?.includes("pdf")
    ) {
      return <PictureAsPdfIcon fontSize="small" color="error" sx={{ mr: 1 }} />;
    }

    // Default icon based on format
    if (
      version.format?.toLowerCase()?.includes("video") ||
      version.format?.toLowerCase()?.includes("mp4")
    ) {
      return <MovieIcon fontSize="small" color="primary" sx={{ mr: 1 }} />;
    } else if (
      version.format?.toLowerCase()?.includes("image") ||
      version.format?.toLowerCase()?.includes("jpg") ||
      version.format?.toLowerCase()?.includes("png")
    ) {
      return <ImageIcon fontSize="small" color="success" sx={{ mr: 1 }} />;
    }

    return <InfoOutlinedIcon fontSize="small" color="action" sx={{ mr: 1 }} />;
  };

  return (
    <List disablePadding sx={{ p: 1 }}>
      {versions.length === 0 ? (
        <Box
          sx={{
            p: 3,
            textAlign: "center",
            bgcolor: alpha(theme.palette.background.paper, 0.4),
            borderRadius: 1,
          }}
        >
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
                "&:hover": {
                  bgcolor: alpha(theme.palette.primary.main, 0.04),
                },
              }}
            >
              <Box sx={{ width: "100%" }}>
                <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                  {getVersionIcon(version)}
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    {version.type.charAt(0).toUpperCase() +
                      version.type.slice(1).toLowerCase()}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ ml: "auto" }}
                  >
                    {version.format}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  <strong>Size:</strong> {version.size || "N/A"}
                </Typography>
                <Box sx={{ display: "flex", mt: 1 }}>
                  <Tooltip title="Download this version">
                    <Button
                      variant="outlined"
                      size="small"
                      sx={{ mr: 1, textTransform: "none" }}
                      onClick={() => handleDownload(version)}
                      disabled={downloadingVersionId === version.id}
                      startIcon={
                        downloadingVersionId === version.id ? (
                          <CircularProgress size={16} />
                        ) : (
                          <DownloadIcon fontSize="small" />
                        )
                      }
                    >
                      {downloadingVersionId === version.id
                        ? "Downloading..."
                        : "Download"}
                    </Button>
                  </Tooltip>
                  {/* <Tooltip title="Preview this version">
                                        <Button
                                            variant="text"
                                            size="small"
                                            sx={{ textTransform: 'none' }}
                                            startIcon={<PreviewIcon fontSize="small" />}
                                        >
                                            Preview
                                        </Button>
                                    </Tooltip> */}
                </Box>
              </Box>
            </ListItem>
            {index < versions.length - 1 && (
              <Divider component="li" sx={{ my: 0.5 }} />
            )}
          </React.Fragment>
        ))
      )}
    </List>
  );
};

// Markers content component
const AssetMarkers: React.FC<AssetMarkersProps> = ({
  markers,
  setMarkers,
  videoViewerRef,
  asset,
  assetType,
  searchTerm,
  clipsMarkersCreated,
  setClipsMarkersCreated,
}) => {
  const theme = useTheme();
  // Store all marker references in a Map
  const markerRefsMap = useRef(new Map<string, PeriodMarker>());
  // State to track editable marker names
  const [markerNames, setMarkerNames] = useState<Record<string, string>>({});
  // Set up subscriptions for all markers
  useEffect(() => {
    const subscriptions: any[] = [];

    // Get all markers from the lane
    if (videoViewerRef?.current) {
      const lane = videoViewerRef.current.getMarkerLane();
      if (lane) {
        markerRefsMap.current.forEach((periodMarker, id) => {
          const subscription = periodMarker.onChange$.subscribe({
            next: (event) => {
              console.log("Marker changed:", {
                id,
                event,
              });

              setMarkers((prevMarkers) =>
                prevMarkers.map((marker) =>
                  marker.id === id
                    ? {
                        ...marker,
                        timeObservation: {
                          start: event.timeObservation.start,
                          end: event.timeObservation.end,
                        },
                      }
                    : marker,
                ),
              );
            },
          });
          subscriptions.push(subscription);
        });
      }
    }

    // Cleanup subscriptions
    return () => {
      subscriptions.forEach((sub) => sub.unsubscribe());
    };
  }, [videoViewerRef, setMarkers]);

  const deleteMarker = (markerId: string) => {
    if (!videoViewerRef?.current) return;

    try {
      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) {
        console.warn("Marker lane is not available");
        return;
      }

      // Get the marker reference
      const markerRef = markerRefsMap.current.get(markerId);
      if (markerRef) {
        // Remove from timeline
        lane.removeMarker(markerId);

        // Remove from markerRefsMap
        markerRefsMap.current.delete(markerId);

        // Remove from markers state
        setMarkers((prevMarkers) =>
          prevMarkers.filter((marker) => marker.id !== markerId),
        );

        // Remove from markerNames if needed
        setMarkerNames((prev) => {
          const newNames = { ...prev };
          delete newNames[markerId];
          return newNames;
        });
      }
    } catch (error) {
      console.error("Error deleting marker:", error);
    }
  };

  const addMarker = () => {
    if (!videoViewerRef?.current) return;

    try {
      const lane = videoViewerRef.current.getMarkerLane();
      if (!lane) {
        console.warn("Marker lane is not available");
        return;
      }

      const currentTime = videoViewerRef.current.getCurrentTime();
      // Generate a unique ID based on timestamp to ensure uniqueness
      const newId = `marker_${Date.now()}_${Math.floor(Math.random() * 1000)}`;

      const periodMarker = new PeriodMarker({
        timeObservation: {
          start: currentTime,
          end: currentTime + 5,
        },
        editable: true,
        id: newId,
        style: {
          ...PERIOD_MARKER_STYLE,
          color: randomHexColor(),
        },
      });

      // Store the marker reference
      markerRefsMap.current.set(newId, periodMarker);

      // Set up subscription for the new marker
      const subscription = periodMarker.onChange$.subscribe({
        next: (event) => {
          console.log("New marker changed:", {
            id: newId,
            event,
          });

          setMarkers((prevMarkers) =>
            prevMarkers.map((marker) =>
              marker.id === newId
                ? {
                    ...marker,
                    timeObservation: {
                      start: event.timeObservation.start,
                      end: event.timeObservation.end,
                    },
                  }
                : marker,
            ),
          );
        },
      });

      lane.addMarker(periodMarker);

      // Use the same default name format, allowing duplicates
      const defaultName = `Marker ${markers.length + 1}`;

      // Add default name for the new marker
      setMarkerNames((prev) => ({
        ...prev,
        [newId]: defaultName,
      }));

      setMarkers((prev) => [
        ...prev,
        {
          id: newId,
          name: defaultName,
          timeObservation: {
            start: currentTime,
            end: currentTime + 5,
          },
          style: {
            color: periodMarker.style.color,
          },
        },
      ]);
    } catch (error) {
      console.error("Error adding marker:", error);
    }
  };

  // Helper function to convert timecode to seconds
  const timecodeToSeconds = (timecode: string): number => {
    // Split the timecode into components
    const [hours, minutes, seconds, frames] = timecode.split(":").map(Number);

    // Assuming 25 frames per second (adjust if different)
    const framesPerSecond = 25;

    // Convert to seconds
    return hours * 3600 + minutes * 60 + seconds + frames / framesPerSecond;
  };

  useEffect(() => {
    if (
      !videoViewerRef?.current ||
      !asset?.clips ||
      !Array.isArray(asset.clips)
    )
      return;

    // Skip if markers have already been created from clips
    if (clipsMarkersCreated) {
      console.log("Clips markers already created, skipping");
      return;
    }

    const timer = setTimeout(() => {
      try {
        const lane = videoViewerRef.current?.getMarkerLane();
        if (!lane) {
          console.warn("Marker lane is not available");
          return;
        }

        const firstThreeClips = asset.clips.slice(0, 3);

        firstThreeClips.forEach((clip, index) => {
          // Convert timecodes to seconds
          const startSeconds = timecodeToSeconds(clip.start_timecode);
          const endSeconds = timecodeToSeconds(clip.end_timecode);

          console.log(`Clip ${index + 1} times:`, {
            original: {
              start: clip.start_timecode,
              end: clip.end_timecode,
            },
            converted: {
              start: startSeconds,
              end: endSeconds,
            },
          });

          // Extract score from clip if available
          const clipScore = clip.score !== undefined ? clip.score : null;

          // Generate a unique ID based on timestamp to ensure uniqueness
          const newId = `clip_${Date.now()}_${index}_${Math.floor(Math.random() * 1000)}`;

          const periodMarker = new PeriodMarker({
            timeObservation: {
              start: startSeconds,
              end: endSeconds,
            },
            editable: true,
            id: newId,
            style: {
              ...PERIOD_MARKER_STYLE,
              color: randomHexColor(),
            },
          });

          markerRefsMap.current.set(newId, periodMarker);

          const subscription = periodMarker.onChange$.subscribe({
            next: (event) => {
              setMarkers((prevMarkers) =>
                prevMarkers.map((marker) =>
                  marker.id === newId
                    ? {
                        ...marker,
                        timeObservation: {
                          start: event.timeObservation.start,
                          end: event.timeObservation.end,
                        },
                      }
                    : marker,
                ),
              );
            },
          });

          lane.addMarker(periodMarker);

          // Use searchTerm for marker names if available, otherwise use default
          const defaultName = searchTerm
            ? `${searchTerm} Clip ${index + 1}`
            : `Marker ${newId}`;

          // Add default name for clip markers
          setMarkerNames((prev) => ({
            ...prev,
            [newId]: defaultName,
          }));

          setMarkers((prev) => [
            ...prev,
            {
              id: newId,
              name: defaultName,
              timeObservation: {
                start: startSeconds,
                end: endSeconds,
              },
              style: {
                color: periodMarker.style.color,
              },
              score: clipScore !== null ? clipScore : undefined, // Add score only if it exists
            },
          ]);
        });

        // Mark that we've created markers from clips
        setClipsMarkersCreated(true);
        console.log("Clips markers created and flag set");
      } catch (error) {
        console.error("Error adding clip markers:", error);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [videoViewerRef, asset, clipsMarkersCreated, setClipsMarkersCreated]);

  return (
    <Box sx={{ p: 2 }}>
      <Button
        variant="contained"
        fullWidth
        sx={{ mt: 1 }}
        startIcon={<BookmarkIcon />}
        onClick={addMarker}
      >
        Add Marker ({markers.length})
      </Button>

      {markers.map((marker, index) => (
        <Box
          key={marker.id}
          sx={{
            mt: 2,
            p: 2,
            pb: 1.5,
            bgcolor: alpha(marker.style.color, 0.1),
            borderRadius: 1,
            border: `1px solid ${alpha(marker.style.color, 0.2)}`,
            position: "relative",
          }}
        >
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 1,
            }}
          >
            <TextField
              variant="standard"
              value={
                marker.id in markerNames
                  ? markerNames[marker.id]
                  : marker.name || `Marker ${marker.id}`
              }
              onChange={(e) => {
                const newName = e.target.value;

                // Update the UI state
                setMarkerNames((prev) => ({
                  ...prev,
                  [marker.id]: newName,
                }));

                // Update the marker state
                setMarkers((prevMarkers) =>
                  prevMarkers.map((m) =>
                    m.id === marker.id ? { ...m, name: newName } : m,
                  ),
                );
              }}
              sx={{
                width: "calc(100% - 40px)",
                "& .MuiInput-root": {
                  fontWeight: "bold",
                },
              }}
            />
            <Tooltip title="Delete marker">
              <IconButton
                size="small"
                onClick={() => deleteMarker(marker.id)}
                sx={{
                  ml: 1,
                  padding: "6px",
                  color: "text.secondary",
                  "&:hover": {
                    color: "error.main",
                    bgcolor: alpha(theme.palette.error.main, 0.1),
                  },
                }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          <Typography variant="body2">
            <b>IN:</b>{" "}
            {videoViewerRef?.current?.formatToTimecode(
              marker.timeObservation.start,
            )}
          </Typography>
          <Typography variant="body2">
            <b>OUT:</b>{" "}
            {videoViewerRef?.current?.formatToTimecode(
              marker.timeObservation.end,
            )}
          </Typography>
          {marker.score !== undefined && (
            <Typography variant="body2">
              <b>Score:</b>{" "}
              {Number(marker.score)
                .toFixed(10)
                .replace(/\.?0+$/, "")}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
};

// Collaboration content component
const AssetCollaboration: React.FC<AssetCollaborationProps> = ({
  comments = [],
  onAddComment,
}) => {
  const [newComment, setNewComment] = useState("");
  const theme = useTheme();

  const handleSubmitComment = () => {
    if (newComment.trim() && onAddComment) {
      onAddComment(newComment);
      setNewComment("");
    }
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
        {comments.length === 0 ? (
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              textAlign: "center",
              bgcolor: alpha(theme.palette.background.paper, 0.4),
            }}
          >
            <GroupsIcon
              color="disabled"
              sx={{ fontSize: 40, mb: 1, opacity: 0.7 }}
            />
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
                  bgcolor:
                    index % 2 === 0
                      ? "transparent"
                      : alpha(theme.palette.background.paper, 0.4),
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
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
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
                      sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}
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
            "& .MuiOutlinedInput-root": {
              backgroundColor: theme.palette.background.paper,
            },
          }}
        />
        <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
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
  const { t } = useTranslation();

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
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: theme.palette.info.main,
            boxShadow: `0 4px 8px ${alpha(theme.palette.info.main, 0.15)}`,
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
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
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: theme.palette.warning.main,
            boxShadow: `0 4px 8px ${alpha(theme.palette.warning.main, 0.15)}`,
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
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
          {t("pipelines.viewAll", "View All Pipelines")}
        </Button>
      </Tooltip>
    </Box>
  );
};

// Activity content component
const AssetActivity: React.FC<AssetActivityProps> = () => {
  const theme = useTheme();
  const activities = [
    {
      user: "System",
      action: "Created asset",
      timestamp: "2023-11-15 09:30:22",
      icon: <PersonIcon color="primary" />,
    },
    {
      user: "John Doe",
      action: "Added to collection",
      timestamp: "2023-11-15 10:15:43",
      icon: <PersonIcon color="primary" />,
    },
    {
      user: "AI Pipeline",
      action: "Generated metadata",
      timestamp: "2023-11-15 11:22:17",
      icon: <TimelineIcon color="secondary" />,
    },
    {
      user: "Jane Smith",
      action: "Added comment",
      timestamp: "2023-11-15 14:05:36",
      icon: <PersonIcon color="primary" />,
    },
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
                "&:hover": {
                  bgcolor: alpha(theme.palette.background.paper, 0.6),
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{activity.icon}</ListItemIcon>
              <ListItemText
                primary={activity.action}
                secondary={
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      mt: 0.5,
                    }}
                  >
                    <Typography variant="caption" component="span">
                      {activity.user}
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      component="span"
                    >
                      {activity.timestamp}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            {index < activities.length - 1 && (
              <Divider component="li" sx={{ my: 0.5 }} />
            )}
          </React.Fragment>
        ))}
      </List>

      <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
        <Tooltip title="Load more activities">
          <Button size="small" color="primary">
            Load More
          </Button>
        </Tooltip>
      </Box>
    </Box>
  );
};
export const AssetSidebar: React.FC<AssetSidebarProps> = (props) => {
  const {
    videoViewerRef,
    versions = [],
    comments = [],
    onAddComment,
    assetId,
    asset,
    assetType,
    searchTerm,
  } = props;
  const [currentTab, setCurrentTab] = useState(0);
  const theme = useTheme();
  const [markers, setMarkers] = useState<MarkerInfo[]>([]);
  const [clipsMarkersCreated, setClipsMarkersCreated] = useState(false);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };
  useEffect(() => {
    console.log("Parent markers state:", markers);
  }, [markers]);

  return (
    <RightSidebar>
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Tabs navigation - now with fixed height and no scroll */}
        <Box
          sx={{
            borderBottom: 1,
            borderColor: "divider",
            bgcolor: alpha(theme.palette.background.default, 0.4),
          }}
        >
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            variant="fullWidth"
            aria-label="asset sidebar tabs"
            sx={{
              minHeight: 40,
              "& .MuiTab-root": {
                minHeight: 40,
                textTransform: "none",
                fontSize: "0.75rem",
                fontWeight: 500,
                opacity: 0.7,
                transition: "all 0.2s",
                padding: "6px 8px",
                minWidth: "auto",
                "&.Mui-selected": {
                  opacity: 1,
                  fontWeight: 600,
                  backgroundColor: alpha(theme.palette.primary.main, 0.08),
                },
              },
              "& .MuiTabs-indicator": {
                height: 2,
                borderTopLeftRadius: 2,
                borderTopRightRadius: 2,
              },
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
                    "& .MuiBadge-badge": {
                      fontSize: "0.65rem",
                      height: 16,
                      minWidth: 16,
                      padding: "0 4px",
                    },
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
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          <Box
            role="tabpanel"
            hidden={currentTab !== 0}
            id="sidebar-tabpanel-0"
            aria-labelledby="sidebar-tab-0"
            sx={{ height: "100%", overflow: "auto" }}
          >
            {currentTab === 0 && (
              <AssetMarkers
                videoViewerRef={videoViewerRef}
                markers={markers}
                setMarkers={setMarkers}
                asset={asset}
                assetType={assetType}
                searchTerm={searchTerm}
                clipsMarkersCreated={clipsMarkersCreated}
                setClipsMarkersCreated={setClipsMarkersCreated}
              />
            )}
          </Box>

          <Box
            role="tabpanel"
            hidden={currentTab !== 1}
            id="sidebar-tabpanel-1"
            aria-labelledby="sidebar-tab-1"
            sx={{ height: "100%", overflow: "auto" }}
          >
            {currentTab === 1 && (
              <AssetVersions
                versions={versions.map((v) => {
                  // Helper function to format file size in a friendly way
                  const formatFileSize = (bytes: number): string => {
                    if (bytes === 0) return "0 B";

                    const k = 1024;
                    const sizes = ["B", "KB", "MB", "GB", "TB"];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));

                    const size = bytes / Math.pow(k, i);

                    // Format with appropriate decimal places
                    if (i === 0) return `${size} B`; // Bytes - no decimals
                    if (i === 1) return `${Math.round(size)} KB`; // KB - no decimals
                    if (i === 2) return `${size.toFixed(1)} MB`; // MB - 1 decimal
                    return `${size.toFixed(2)} ${sizes[i]}`; // GB+ - 2 decimals
                  };

                  // Use the existing fileSize property from the version object
                  let size = null;

                  if (v.fileSize) {
                    // If fileSize is already formatted (contains 'KB', 'MB', etc.), check if it needs reformatting
                    if (
                      typeof v.fileSize === "string" &&
                      (v.fileSize.includes("KB") ||
                        v.fileSize.includes("MB") ||
                        v.fileSize.includes("GB"))
                    ) {
                      // Extract the numeric value and reformat it
                      const numericValue = parseFloat(v.fileSize);
                      if (!isNaN(numericValue)) {
                        // Convert back to bytes based on unit, then reformat
                        let bytes = numericValue;
                        if (v.fileSize.includes("KB")) bytes *= 1024;
                        else if (v.fileSize.includes("MB"))
                          bytes *= 1024 * 1024;
                        else if (v.fileSize.includes("GB"))
                          bytes *= 1024 * 1024 * 1024;
                        size = formatFileSize(bytes);
                      } else {
                        size = v.fileSize; // Keep original if parsing fails
                      }
                    } else {
                      // If fileSize is raw bytes, format it
                      const bytes = parseFloat(v.fileSize);
                      size = formatFileSize(bytes);
                    }
                  }

                  return {
                    ...v,
                    assetId: assetId,
                    size: size,
                  };
                })}
              />
            )}
          </Box>
        </Box>
      </Box>
    </RightSidebar>
  );
};

export default AssetSidebar;
