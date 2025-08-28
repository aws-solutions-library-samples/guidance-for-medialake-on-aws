import React from "react";
import { TextField, Button, Box, Tooltip, IconButton } from "@mui/material";
import { Search as SearchIcon, Help as HelpIcon } from "@mui/icons-material";

interface SearchBarProps {
  searchQuery: string;
  onSearchChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSearchSubmit: () => void;
}

const searchHelpText = `
Search Tips:
• Use type: to filter by media type (e.g., type:image, type:video)
• Use format: to filter by format (e.g., format:jpg, format:mp4)
• Use size: to filter by file size (e.g., size:>1GB, size:<500MB)
• Use date: to filter by date (e.g., date:>2024-01-01)
• Use metadata: to filter by metadata (e.g., metadata:resolution:1080p)

Examples:
• "sunset type:image format:jpg"
• "presentation type:video size:>1GB"
• "metadata:resolution:1080p type:video"
`;

const SearchBar: React.FC<SearchBarProps> = ({
  searchQuery,
  onSearchChange,
  onSearchSubmit,
}) => (
  <Box sx={{ display: "flex", flexGrow: 1, mr: 2, alignItems: "center" }}>
    <TextField
      label="Search"
      variant="outlined"
      size="small"
      value={searchQuery}
      onChange={onSearchChange}
      onKeyDown={(e) => e.key === "Enter" && onSearchSubmit()}
      placeholder="Search (e.g., sunset type:image)"
      sx={{ flexGrow: 1, mr: 2, bgcolor: "background.paper" }}
      helperText="Use keywords like type:, format:, size:, date:, metadata: to filter results"
    />
    <Tooltip
      title={<pre style={{ whiteSpace: "pre-wrap" }}>{searchHelpText}</pre>}
      placement="bottom-start"
      sx={{ maxWidth: "none" }}
    >
      <IconButton size="small" sx={{ mr: 1 }}>
        <HelpIcon />
      </IconButton>
    </Tooltip>
    <Button
      variant="contained"
      startIcon={<SearchIcon />}
      onClick={onSearchSubmit}
    >
      Search
    </Button>
  </Box>
);

export default React.memo(SearchBar);
