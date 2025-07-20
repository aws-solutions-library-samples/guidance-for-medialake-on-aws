import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
} from "@mui/material";
import HistoryIcon from "@mui/icons-material/History";
import { formatFileSize } from "../../utils/imageUtils";

interface Representation {
  id: string;
  src: string;
  type: string;
  format: string;
  fileSize: string;
  description: string;
}

interface AssetVersionsProps {
  versions: Representation[];
}

const AssetVersions: React.FC<AssetVersionsProps> = ({ versions }) => {
  return (
    <Box sx={{ p: 2 }}>
      <List>
        {versions.map((version, index) => (
          <ListItem
            key={version.id}
            sx={{
              mb: 2,
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              flexDirection: "column",
              alignItems: "flex-start",
              p: 2,
            }}
          >
            <Box
              sx={{ display: "flex", alignItems: "flex-start", width: "100%" }}
            >
              <ListItemIcon sx={{ minWidth: 40, mt: 0.5 }}>
                <HistoryIcon />
              </ListItemIcon>
              <Box sx={{ flex: 1 }}>
                <Typography
                  variant="subtitle1"
                  sx={{ textTransform: "capitalize" }}
                >
                  {version.type}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {version.format} • {version.fileSize}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {version.description}
                </Typography>
              </Box>
            </Box>
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default AssetVersions;
