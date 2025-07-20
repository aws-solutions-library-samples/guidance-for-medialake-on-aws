import React from "react";
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  useTheme,
  Chip,
  Stack,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { Role } from "../../../../api/types/api.types";

interface RoleListProps {
  roles: Role[];
  onEditRole: (role: Role) => void;
  onDeleteRole: (roleId: string) => void;
}

const RoleList: React.FC<RoleListProps> = ({
  roles,
  onEditRole,
  onDeleteRole,
}) => {
  const theme = useTheme();

  return (
    <Stack spacing={2}>
      {roles.map((role) => (
        <Paper
          key={role.id}
          sx={{
            p: 2,
            "&:hover": {
              backgroundColor: theme.palette.action.hover,
            },
          }}
        >
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <Box>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {role.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {role.description}
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {role.permissions.map((permission) => (
                  <Chip
                    key={permission}
                    label={permission
                      .split("_")
                      .map(
                        (word) => word.charAt(0) + word.slice(1).toLowerCase(),
                      )
                      .join(" ")}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Box>
            <Box sx={{ display: "flex", gap: 1 }}>
              <Tooltip title="Edit Role">
                <IconButton
                  size="small"
                  onClick={() => onEditRole(role)}
                  sx={{
                    color: theme.palette.primary.main,
                  }}
                >
                  <EditIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete Role">
                <IconButton
                  size="small"
                  onClick={() => onDeleteRole(role.id)}
                  sx={{
                    color: theme.palette.error.main,
                  }}
                >
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Paper>
      ))}
    </Stack>
  );
};

export default RoleList;
