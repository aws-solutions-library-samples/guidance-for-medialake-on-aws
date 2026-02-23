// components/TopBar/Chat/ChatMessage.tsx
import React from "react";
import { Typography } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { ChatMessage as ChatMessageType } from "../types";

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const theme = useTheme();
  return (
    <Typography
      sx={{
        alignSelf: message.sender === "user" ? "flex-end" : "flex-start",
        bgcolor:
          message.sender === "user"
            ? alpha(theme.palette.primary.main, 0.1)
            : theme.palette.action.hover,
        borderRadius: "8px",
        padding: "8px",
        margin: "4px 0",
        maxWidth: "80%",
        display: "inline-block",
      }}
    >
      {message.text}
    </Typography>
  );
};

export default React.memo(ChatMessage);
