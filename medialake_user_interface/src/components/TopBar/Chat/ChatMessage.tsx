// components/TopBar/Chat/ChatMessage.tsx
import React from "react";
import { Typography } from "@mui/material";
import { ChatMessage as ChatMessageType } from "../types";

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => (
  <Typography
    sx={{
      alignSelf: message.sender === "user" ? "flex-end" : "flex-start",
      bgcolor: message.sender === "user" ? "#e0f7fa" : "#f1f1f1",
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

export default React.memo(ChatMessage);
