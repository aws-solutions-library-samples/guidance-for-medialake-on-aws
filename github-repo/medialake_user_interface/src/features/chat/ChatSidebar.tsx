import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Typography,
  IconButton,
  Divider,
  Slide,
  Fade,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import {
  useChat,
  ChatMessage as ChatMessageType,
} from "../../contexts/ChatContext";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { useTheme, alpha } from "@mui/material/styles";

const SIDEBAR_WIDTH = 350;

const ChatSidebar: React.FC = () => {
  const { isOpen, messages, closeChat, clearHistory } = useChat();
  const theme = useTheme();
  const [isResizing, setIsResizing] = useState(false);
  const [width, setWidth] = useState(SIDEBAR_WIDTH);
  const resizeHandleRef = useRef<HTMLDivElement | null>(null);

  // Reference to scroll to bottom when new messages are added
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Save width to localStorage when it changes
  useEffect(() => {
    if (width !== SIDEBAR_WIDTH) {
      localStorage.setItem("chatSidebarWidth", width.toString());
    }
  }, [width]);

  // Load saved width on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem("chatSidebarWidth");
    if (savedWidth) {
      const parsedWidth = parseInt(savedWidth, 10);
      if (!isNaN(parsedWidth) && parsedWidth >= 300 && parsedWidth <= 600) {
        setWidth(parsedWidth);
      }
    }
  }, []);

  // Handle resize start
  const handleResizeStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
  };

  // Handle resizing
  useEffect(() => {
    const handleResize = (e: MouseEvent) => {
      if (isResizing && isOpen) {
        // Calculate new width based on mouse position
        const newWidth = window.innerWidth - e.clientX;

        // Apply constraints
        if (newWidth >= 300 && newWidth <= 600) {
          setWidth(newWidth);
        }
      }
    };

    const handleResizeEnd = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleResize);
      document.addEventListener("mouseup", handleResizeEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleResize);
      document.removeEventListener("mouseup", handleResizeEnd);
    };
  }, [isResizing, isOpen]);

  // If the chat is not open, don't render anything
  if (!isOpen) return null;

  return (
    <Slide direction="left" in={isOpen} mountOnEnter unmountOnExit>
      <Box
        sx={{
          width: width,
          flexShrink: 0,
          borderLeft: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          position: "fixed",
          top: 72,
          right: 0,
          height: "calc(100vh - 72px)",
          display: "flex",
          flexDirection: "column",
          zIndex: 1200,
          borderRadius: "16px 0 0 16px",
          boxShadow: (theme) =>
            `0 4px 20px ${alpha(
              theme.palette.common.black,
              theme.palette.mode === "dark" ? 0.5 : 0.1,
            )}`,
          transition: isResizing
            ? "none"
            : (theme) =>
                theme.transitions.create(["width", "box-shadow"], {
                  easing: theme.transitions.easing.easeInOut,
                  duration: theme.transitions.duration.standard,
                }),
          overflow: "hidden",
        }}
      >
        {/* Resize handle */}
        <Box
          ref={resizeHandleRef}
          onMouseDown={handleResizeStart}
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "8px",
            height: "100%",
            cursor: "col-resize",
            zIndex: 1300,
            "&:hover": {
              backgroundColor: (theme) =>
                alpha(theme.palette.primary.main, 0.1),
            },
            "&::after": {
              content: '""',
              position: "absolute",
              top: "50%",
              left: "3px",
              width: "2px",
              height: "40px",
              backgroundColor: (theme) =>
                alpha(theme.palette.primary.main, 0.3),
              borderRadius: "2px",
              transform: "translateY(-50%)",
            },
          }}
        />

        {/* Header */}
        <Box
          sx={{
            p: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid",
            borderColor: "divider",
            bgcolor: (theme) =>
              theme.palette.mode === "dark"
                ? alpha(theme.palette.background.paper, 0.8)
                : alpha(theme.palette.background.paper, 0.95),
            backdropFilter: "blur(8px)",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Chat
          </Typography>
          <Box>
            {messages.length > 0 && (
              <IconButton
                size="small"
                onClick={clearHistory}
                title="Clear chat history"
                sx={{
                  mr: 1,
                  color: "text.secondary",
                  "&:hover": {
                    color: "error.main",
                    bgcolor: (theme) => alpha(theme.palette.error.main, 0.1),
                  },
                }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            )}
            <IconButton
              size="small"
              onClick={closeChat}
              title="Close chat"
              sx={{
                color: "text.secondary",
                "&:hover": {
                  color: "text.primary",
                  bgcolor: (theme) => alpha(theme.palette.text.primary, 0.1),
                },
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        {/* Messages Area */}
        <Box
          sx={{
            flex: 1,
            overflowY: "auto",
            p: 2,
            display: "flex",
            flexDirection: "column",
            bgcolor: (theme) =>
              theme.palette.mode === "dark"
                ? alpha(theme.palette.background.default, 0.3)
                : alpha(theme.palette.background.default, 0.5),
            scrollbarWidth: "thin",
            scrollbarColor: (theme) =>
              `${alpha(theme.palette.text.secondary, 0.3)} transparent`,
            "&::-webkit-scrollbar": {
              width: "6px",
            },
            "&::-webkit-scrollbar-track": {
              background: "transparent",
            },
            "&::-webkit-scrollbar-thumb": {
              background: (theme) => alpha(theme.palette.text.secondary, 0.3),
              borderRadius: "3px",
            },
            "&::-webkit-scrollbar-thumb:hover": {
              background: (theme) => alpha(theme.palette.text.secondary, 0.5),
            },
          }}
        >
          {messages.length === 0 ? (
            <Fade in={true} timeout={800}>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: "text.secondary",
                  textAlign: "center",
                  px: 4,
                }}
              >
                <Typography
                  variant="body1"
                  gutterBottom
                  sx={{ fontWeight: 500 }}
                >
                  No messages yet
                </Typography>
                <Typography variant="body2">
                  Start a conversation by typing a message below.
                </Typography>
              </Box>
            </Fade>
          ) : (
            messages.map((message: ChatMessageType) => (
              <ChatMessage key={message.id} message={message} />
            ))
          )}
          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        <Box
          sx={{
            p: 2,
            borderTop: "1px solid",
            borderColor: "divider",
            bgcolor: (theme) =>
              theme.palette.mode === "dark"
                ? alpha(theme.palette.background.paper, 0.8)
                : alpha(theme.palette.background.paper, 0.95),
            backdropFilter: "blur(8px)",
          }}
        >
          <ChatInput />
        </Box>

        {/* Optional overlay for better UX during resizing */}
        {isResizing && (
          <Box
            sx={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 1199,
              cursor: "col-resize",
            }}
          />
        )}
      </Box>
    </Slide>
  );
};

export default ChatSidebar;
