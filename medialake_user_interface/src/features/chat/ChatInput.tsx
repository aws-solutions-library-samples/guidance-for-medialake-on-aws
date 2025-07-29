import React, { useState, KeyboardEvent, useRef, useEffect } from "react";
import {
  Box,
  TextField,
  IconButton,
  Paper,
  Zoom,
  CircularProgress,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import { useChat } from "../../contexts/ChatContext";
import { useTheme, alpha } from "@mui/material/styles";

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { addMessage, updateLastMessage, isOpen } = useChat();
  const theme = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus the input field when the chat is opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      // Small delay to ensure the animation is complete
      setTimeout(() => {
        inputRef.current?.focus();
      }, 300);
    }
  }, [isOpen]);

  // Handle sending a message
  const handleSendMessage = () => {
    if (message.trim()) {
      // Add the user message to the chat
      addMessage(message.trim(), "user");

      // Clear the input field
      setMessage("");

      // Show loading state
      setIsLoading(true);

      // In a real implementation, you would also:
      // 1. Send the message to a backend API
      // 2. Handle the response and add it as a system message
      // For now, we'll just simulate a system response after a short delay
      addMessage("...", "system", true); // Add a thinking indicator message

      setTimeout(() => {
        // Remove the loading indicator message
        // In a real implementation, you would replace it with the actual response
        setIsLoading(false);
        updateLastMessage(
          "This is a simulated response. In a real implementation, this would come from the backend.",
        );
      }, 1500);
    }
  };

  // Handle pressing Enter to send a message
  const handleKeyPress = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Paper
      elevation={4}
      sx={{
        p: 1.5,
        borderRadius: 3,
        bgcolor: (theme) =>
          theme.palette.mode === "dark"
            ? alpha(theme.palette.background.paper, 0.8)
            : theme.palette.background.paper,
        boxShadow: (theme) =>
          `0 2px 12px ${alpha(
            theme.palette.common.black,
            theme.palette.mode === "dark" ? 0.3 : 0.1,
          )}`,
        transition: (theme) => theme.transitions.create(["box-shadow"]),
        "&:hover": {
          boxShadow: (theme) =>
            `0 4px 16px ${alpha(
              theme.palette.common.black,
              theme.palette.mode === "dark" ? 0.4 : 0.15,
            )}`,
        },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "flex-end" }}>
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Type a message..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          multiline
          maxRows={4}
          inputRef={inputRef}
          disabled={isLoading}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2.5,
              backgroundColor: (theme) =>
                theme.palette.mode === "dark"
                  ? alpha(theme.palette.background.default, 0.3)
                  : alpha(theme.palette.background.default, 0.5),
              transition: (theme) =>
                theme.transitions.create(["background-color", "box-shadow"]),
              "&:hover": {
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark"
                    ? alpha(theme.palette.background.default, 0.4)
                    : alpha(theme.palette.background.default, 0.7),
              },
              "&.Mui-focused": {
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark"
                    ? alpha(theme.palette.background.default, 0.5)
                    : alpha(theme.palette.background.default, 0.8),
                boxShadow: (theme) =>
                  `0 0 0 2px ${alpha(theme.palette.primary.main, 0.25)}`,
              },
            },
            "& .MuiInputBase-input": {
              fontSize: "0.95rem",
              lineHeight: 1.5,
            },
          }}
          InputProps={{
            sx: {
              py: 1.25,
              px: 2,
            },
          }}
        />
        <Zoom in={!!message.trim() || isLoading} timeout={200}>
          <IconButton
            color="primary"
            onClick={handleSendMessage}
            disabled={!message.trim() || isLoading}
            sx={{
              ml: 1,
              mb: 0.5,
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
              "&:hover": {
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.2),
              },
              "&.Mui-disabled": {
                bgcolor: "transparent",
              },
              transition: (theme) =>
                theme.transitions.create(["background-color", "transform"]),
              transform: message.trim() ? "scale(1)" : "scale(0.9)",
            }}
          >
            {isLoading ? (
              <CircularProgress size={20} thickness={5} />
            ) : (
              <SendIcon />
            )}
          </IconButton>
        </Zoom>
      </Box>
    </Paper>
  );
};

export default ChatInput;
