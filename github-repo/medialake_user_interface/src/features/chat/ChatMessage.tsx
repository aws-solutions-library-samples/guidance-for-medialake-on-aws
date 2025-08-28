import React, { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Avatar,
  CircularProgress,
  Fade,
} from "@mui/material";
import { ChatMessage as ChatMessageType } from "../../contexts/ChatContext";
import { useTheme, alpha } from "@mui/material/styles";
import PersonIcon from "@mui/icons-material/Person";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import ImageIcon from "@mui/icons-material/Image";
import VideocamIcon from "@mui/icons-material/Videocam";
import AudioFileIcon from "@mui/icons-material/AudioFile";

interface ChatMessageProps {
  message: ChatMessageType;
}

// Helper function to detect media URLs in message content
const detectMediaType = (
  content: string,
): { type: "text" | "image" | "video" | "audio"; url?: string } => {
  // Simple regex to detect image URLs
  const imageRegex = /(https?:\/\/.*\.(?:png|jpg|jpeg|gif|webp))/i;
  // Simple regex to detect video URLs
  const videoRegex = /(https?:\/\/.*\.(?:mp4|webm|ogg|mov))/i;
  // Simple regex to detect audio URLs
  const audioRegex = /(https?:\/\/.*\.(?:mp3|wav|ogg|m4a))/i;

  const imageMatch = content.match(imageRegex);
  if (imageMatch) return { type: "image", url: imageMatch[0] };

  const videoMatch = content.match(videoRegex);
  if (videoMatch) return { type: "video", url: videoMatch[0] };

  const audioMatch = content.match(audioRegex);
  if (audioMatch) return { type: "audio", url: audioMatch[0] };

  return { type: "text" };
};

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const theme = useTheme();
  const isUser = message.sender === "user";
  const [mediaLoaded, setMediaLoaded] = useState(false);
  const [mediaError, setMediaError] = useState(false);

  // Detect if the message contains media
  const mediaContent = detectMediaType(message.content);
  const hasMedia = mediaContent.type !== "text";

  // Format the timestamp
  const formattedTime = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(message.timestamp);

  // Format the date if it's not today
  const today = new Date();
  const messageDate = message.timestamp;
  const isToday = today.toDateString() === messageDate.toDateString();

  const formattedDate = isToday
    ? "Today"
    : new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
      }).format(messageDate);

  // Handle media loading events
  const handleMediaLoad = () => {
    setMediaLoaded(true);
  };

  const handleMediaError = () => {
    setMediaError(true);
    setMediaLoaded(true); // Still mark as loaded to remove loading indicator
  };

  return (
    <Fade in={true} timeout={300}>
      <Box
        sx={{
          display: "flex",
          flexDirection: isUser ? "row-reverse" : "row",
          mb: 2.5,
          gap: 1.5,
          maxWidth: "100%",
        }}
      >
        {/* Avatar for the message sender */}
        <Avatar
          sx={{
            bgcolor: isUser
              ? theme.palette.primary.main
              : theme.palette.secondary.main,
            width: 36,
            height: 36,
            boxShadow: (theme) =>
              `0 2px 8px ${alpha(theme.palette.common.black, 0.15)}`,
            mt: 0.5,
          }}
        >
          {isUser ? (
            <PersonIcon fontSize="small" />
          ) : (
            <SmartToyIcon fontSize="small" />
          )}
        </Avatar>

        {/* Message content */}
        <Box
          sx={{
            maxWidth: "75%",
            minWidth: hasMedia ? "200px" : "auto",
          }}
        >
          <Paper
            elevation={2}
            sx={{
              p: 1.5,
              borderRadius: 2.5,
              bgcolor: isUser
                ? alpha(
                    theme.palette.primary.main,
                    theme.palette.mode === "dark" ? 0.3 : 0.1,
                  )
                : theme.palette.mode === "dark"
                  ? alpha(theme.palette.background.paper, 0.4)
                  : alpha(theme.palette.background.paper, 0.7),
              borderTopRightRadius: isUser ? 0 : undefined,
              borderTopLeftRadius: !isUser ? 0 : undefined,
              boxShadow: (theme) =>
                `0 2px 10px ${alpha(
                  theme.palette.common.black,
                  theme.palette.mode === "dark" ? 0.3 : 0.08,
                )}`,
              overflow: "hidden",
              position: "relative",
            }}
          >
            {/* Text content */}
            {(!hasMedia || mediaContent.type === "text") && (
              <Typography
                variant="body1"
                sx={{
                  color: isUser
                    ? theme.palette.mode === "dark"
                      ? theme.palette.primary.light
                      : theme.palette.primary.dark
                    : "text.primary",
                  fontWeight: 400,
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {message.content}
              </Typography>
            )}

            {/* Image content */}
            {mediaContent.type === "image" && mediaContent.url && (
              <Box
                sx={{ position: "relative", width: "100%", minHeight: "150px" }}
              >
                {!mediaLoaded && !mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                )}

                {mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      alignItems: "center",
                      p: 2,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <ImageIcon
                      sx={{ fontSize: 40, color: "text.secondary", mb: 1 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Failed to load image
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ wordBreak: "break-all" }}
                    >
                      {mediaContent.url}
                    </Typography>
                  </Box>
                )}

                <Box
                  component="img"
                  src={mediaContent.url}
                  alt="Image in chat"
                  onLoad={handleMediaLoad}
                  onError={handleMediaError}
                  sx={{
                    display: mediaError ? "none" : "block",
                    maxWidth: "100%",
                    maxHeight: "300px",
                    borderRadius: 1,
                    mt: 1,
                    mb: 1,
                  }}
                />
              </Box>
            )}

            {/* Video content */}
            {mediaContent.type === "video" && mediaContent.url && (
              <Box
                sx={{ position: "relative", width: "100%", minHeight: "150px" }}
              >
                {!mediaLoaded && !mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                )}

                {mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      alignItems: "center",
                      p: 2,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <VideocamIcon
                      sx={{ fontSize: 40, color: "text.secondary", mb: 1 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Failed to load video
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ wordBreak: "break-all" }}
                    >
                      {mediaContent.url}
                    </Typography>
                  </Box>
                )}

                <Box
                  component="video"
                  src={mediaContent.url}
                  controls
                  onLoadedData={handleMediaLoad}
                  onError={handleMediaError}
                  sx={{
                    display: mediaError ? "none" : "block",
                    width: "100%",
                    maxHeight: "300px",
                    borderRadius: 1,
                    mt: 1,
                    mb: 1,
                  }}
                />
              </Box>
            )}

            {/* Audio content */}
            {mediaContent.type === "audio" && mediaContent.url && (
              <Box
                sx={{ position: "relative", width: "100%", minHeight: "50px" }}
              >
                {!mediaLoaded && !mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      p: 2,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                )}

                {mediaError && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      alignItems: "center",
                      p: 2,
                      bgcolor: "rgba(0,0,0,0.05)",
                      borderRadius: 1,
                    }}
                  >
                    <AudioFileIcon
                      sx={{ fontSize: 40, color: "text.secondary", mb: 1 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Failed to load audio
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ wordBreak: "break-all" }}
                    >
                      {mediaContent.url}
                    </Typography>
                  </Box>
                )}

                <Box
                  component="audio"
                  src={mediaContent.url}
                  controls
                  onLoadedData={handleMediaLoad}
                  onError={handleMediaError}
                  sx={{
                    display: mediaError ? "none" : "block",
                    width: "100%",
                    mt: 1,
                    mb: 1,
                  }}
                />
              </Box>
            )}

            {/* System message "thinking" indicator */}
            {message.sender === "system" &&
              (message.isThinking || message.content.includes("...")) && (
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    mt: 0.5,
                    gap: 0.5,
                  }}
                >
                  <Box
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor: "text.secondary",
                      animation: "pulse 1s infinite",
                      "@keyframes pulse": {
                        "0%": { opacity: 0.3 },
                        "50%": { opacity: 1 },
                        "100%": { opacity: 0.3 },
                      },
                      animationDelay: "0s",
                    }}
                  />
                  <Box
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor: "text.secondary",
                      animation: "pulse 1s infinite",
                      "@keyframes pulse": {
                        "0%": { opacity: 0.3 },
                        "50%": { opacity: 1 },
                        "100%": { opacity: 0.3 },
                      },
                      animationDelay: "0.33s",
                    }}
                  />
                  <Box
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor: "text.secondary",
                      animation: "pulse 1s infinite",
                      "@keyframes pulse": {
                        "0%": { opacity: 0.3 },
                        "50%": { opacity: 1 },
                        "100%": { opacity: 0.3 },
                      },
                      animationDelay: "0.66s",
                    }}
                  />
                </Box>
              )}
          </Paper>

          {/* Timestamp */}
          <Typography
            variant="caption"
            sx={{
              display: "block",
              mt: 0.5,
              color: "text.secondary",
              textAlign: isUser ? "right" : "left",
              fontSize: "0.7rem",
              opacity: 0.8,
            }}
          >
            {formattedDate !== "Today" && `${formattedDate}, `}
            {formattedTime}
          </Typography>
        </Box>
      </Box>
    </Fade>
  );
};

export default ChatMessage;
