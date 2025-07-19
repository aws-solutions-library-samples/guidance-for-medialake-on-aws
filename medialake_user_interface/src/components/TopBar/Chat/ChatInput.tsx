// components/TopBar/Chat/ChatInput.tsx
import React from "react";
import { Box, TextField, IconButton } from "@mui/material";
import { Send as SendIcon, Close as CloseIcon } from "@mui/icons-material";

interface ChatInputProps {
  value: string;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: () => void;
  onClose: () => void;
}

const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSubmit,
  onClose,
}) => (
  <Box sx={{ p: 2, borderTop: "1px solid rgba(0, 0, 0, 0.12)" }}>
    <Box sx={{ display: "flex", alignItems: "center" }}>
      <TextField
        variant="outlined"
        size="small"
        value={value}
        onChange={onChange}
        placeholder="Type your message..."
        sx={{ flexGrow: 1, mr: 1 }}
      />
      <IconButton
        onClick={onSubmit}
        sx={{
          mr: 1,
          bgcolor: "primary.main",
          color: "white",
          "&:hover": { bgcolor: "primary.dark" },
        }}
      >
        <SendIcon />
      </IconButton>
      <IconButton
        onClick={onClose}
        sx={{
          bgcolor: "error.main",
          color: "white",
          "&:hover": { bgcolor: "error.dark" },
        }}
      >
        <CloseIcon />
      </IconButton>
    </Box>
  </Box>
);

export default React.memo(ChatInput);
