import React, { useState } from "react";
import {
  Box,
  Paper,
  Typography,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  useTheme,
  LinearProgress,
  Alert,
  Card,
  CardContent,
  Tooltip,
} from "@mui/material";
import {
  PersonAdd as PersonAddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Storage as StorageIcon,
  CloudUpload as CloudUploadIcon,
  Speed as SpeedIcon,
  Group as GroupIcon,
  BarChart as BarChartIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  lastActive: string;
}

interface SystemMetric {
  label: string;
  value: string;
  percentage: number;
  icon: React.ReactNode;
  color: string;
}

const mockUsers: User[] = [
  {
    id: "1",
    name: "John Doe",
    email: "john@example.com",
    role: "Admin",
    status: "Active",
    lastActive: "2024-01-20",
  },
  {
    id: "2",
    name: "Jane Smith",
    email: "jane@example.com",
    role: "Editor",
    status: "Active",
    lastActive: "2024-01-19",
  },
  {
    id: "3",
    name: "Mike Johnson",
    email: "mike@example.com",
    role: "Viewer",
    status: "Inactive",
    lastActive: "2024-01-15",
  },
];

const AdminSettings: React.FC = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);

  const systemMetrics: SystemMetric[] = [
    {
      label: t("admin.metrics.storageUsage", "Storage Usage"),
      value: "789.5 GB / 1 TB",
      percentage: 78.95,
      icon: <StorageIcon />,
      color: theme.palette.primary.main,
    },
    {
      label: t("admin.metrics.apiUsage", "API Usage"),
      value: "85.2K / 100K calls",
      percentage: 85.2,
      icon: <CloudUploadIcon />,
      color: theme.palette.success.main,
    },
    {
      label: t("admin.metrics.activeUsers", "Active Users"),
      value: "45 / 50 seats",
      percentage: 90,
      icon: <GroupIcon />,
      color: theme.palette.warning.main,
    },
    {
      label: t("admin.metrics.systemLoad", "System Load"),
      value: "65%",
      percentage: 65,
      icon: <SpeedIcon />,
      color: theme.palette.info.main,
    },
  ];

  const handleDeleteUser = (userId: string) => {
    // TODO: Implement user deletion
    setError(
      t(
        "admin.errors.userDeletionNotImplemented",
        "User deletion is not implemented yet.",
      ),
    );
  };

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* System Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {systemMetrics.map((metric) => (
          <Grid item xs={12} sm={6} md={3} key={metric.label}>
            <Card
              elevation={0}
              sx={{
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: "12px",
                height: "100%",
              }}
            >
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                  <Box
                    sx={{
                      p: 1,
                      borderRadius: "8px",
                      backgroundColor: `${metric.color}15`,
                      color: metric.color,
                      mr: 1,
                    }}
                  >
                    {metric.icon}
                  </Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    {metric.label}
                  </Typography>
                </Box>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  {metric.value}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metric.percentage}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    backgroundColor: `${metric.color}20`,
                    "& .MuiLinearProgress-bar": {
                      borderRadius: 3,
                      backgroundColor: metric.color,
                    },
                  }}
                />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* User Management */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: "12px",
          border: `1px solid ${theme.palette.divider}`,
          mb: 4,
        }}
      >
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 3,
          }}
        >
          <Typography variant="h6">
            {t("users.title", "User Management")}
          </Typography>
          <Button
            variant="contained"
            startIcon={<PersonAddIcon />}
            onClick={() =>
              setError(
                t(
                  "admin.errors.userCreationNotImplemented",
                  "User creation is not implemented yet.",
                ),
              )
            }
          >
            {t("actions.addUser", "Add User")}
          </Button>
        </Box>

        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>{t("columns.firstName", "Name")}</TableCell>
                <TableCell>{t("columns.email", "Email")}</TableCell>
                <TableCell>{t("roles.title", "Role")}</TableCell>
                <TableCell>{t("columns.status", "Status")}</TableCell>
                <TableCell>
                  {t("admin.columns.lastActive", "Last Active")}
                </TableCell>
                <TableCell align="right">
                  {t("columns.actions", "Actions")}
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mockUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={user.role}
                      size="small"
                      sx={{
                        backgroundColor:
                          user.role === "Admin"
                            ? `${theme.palette.error.main}15`
                            : `${theme.palette.primary.main}15`,
                        color:
                          user.role === "Admin"
                            ? theme.palette.error.main
                            : theme.palette.primary.main,
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={user.status}
                      size="small"
                      sx={{
                        backgroundColor:
                          user.status === "Active"
                            ? `${theme.palette.success.main}15`
                            : `${theme.palette.grey[500]}15`,
                        color:
                          user.status === "Active"
                            ? theme.palette.success.main
                            : theme.palette.grey[500],
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    {new Date(user.lastActive).toLocaleDateString()}
                  </TableCell>
                  <TableCell align="right">
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: 1,
                      }}
                    >
                      <Tooltip title={t("actions.edit", "Edit user")}>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setError(
                              t(
                                "admin.errors.userEditingNotImplemented",
                                "User editing is not implemented yet.",
                              ),
                            )
                          }
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t("actions.delete", "Delete user")}>
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteUser(user.id)}
                          sx={{ color: theme.palette.error.main }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* System Settings */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: "12px",
          border: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Typography variant="h6" sx={{ mb: 3 }}>
          {t("settings.systemSettings.title", "System Settings")}
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<BarChartIcon />}
              onClick={() =>
                setError(
                  t(
                    "admin.errors.analyticsExportNotImplemented",
                    "Analytics export is not implemented yet.",
                  ),
                )
              }
            >
              {t("admin.buttons.exportAnalytics", "Export Analytics")}
            </Button>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Button
              fullWidth
              variant="outlined"
              color="error"
              onClick={() =>
                setError(
                  t(
                    "admin.errors.systemResetNotImplemented",
                    "System reset is not implemented yet.",
                  ),
                )
              }
            >
              {t("admin.buttons.resetSystem", "Reset System")}
            </Button>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default AdminSettings;
