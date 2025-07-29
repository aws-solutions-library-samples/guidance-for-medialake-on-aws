import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Avatar,
  Grid,
  Divider,
  Switch,
  FormControlLabel,
  IconButton,
  useTheme,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material";
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  PhotoCamera as PhotoCameraIcon,
  Notifications as NotificationsIcon,
  Security as SecurityIcon,
  Language as LanguageIcon,
  Palette as PaletteIcon,
  Schedule as ScheduleIcon,
} from "@mui/icons-material";
import { useTimezone } from "../../contexts/TimezoneContext";
import { useTranslation } from "react-i18next";

interface UserProfileData {
  firstName: string;
  lastName: string;
  email: string;
  jobTitle: string;
  organization: string;
  language: string;
  theme: "light" | "dark";
  notifications: {
    email: boolean;
    push: boolean;
    updates: boolean;
  };
}

// Common timezones list
const COMMON_TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "America/Toronto",
  "America/Vancouver",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Rome",
  "Europe/Madrid",
  "Asia/Dubai",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Australia/Sydney",
  "Pacific/Auckland",
];

const UserProfile: React.FC = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { timezone, setTimezone } = useTimezone();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileData, setProfileData] = useState<UserProfileData>({
    firstName: "John",
    lastName: "Doe",
    email: "john.doe@example.com",
    jobTitle: "Media Manager",
    organization: "MediaLake Inc.",
    language: "English",
    theme: "light",
    notifications: {
      email: true,
      push: true,
      updates: false,
    },
  });

  const handleSave = () => {
    try {
      // TODO: Implement save functionality
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(
        t(
          "errors.saveFailed",
          "Failed to save profile changes. Please try again.",
        ),
      );
    }
  };

  const handleCancel = () => {
    setEditing(false);
    setError(null);
  };

  const formatTimezone = (tz: string) => {
    return tz.replace(/_/g, " ").replace(/\//g, " / ");
  };

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Profile Information */}
        <Grid item xs={12} md={8}>
          <Paper
            elevation={0}
            sx={{
              p: 3,
              borderRadius: "12px",
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Box
              sx={{ display: "flex", justifyContent: "space-between", mb: 3 }}
            >
              <Typography variant="h6">{t("common.profile")}</Typography>
              {!editing ? (
                <Button
                  startIcon={<EditIcon />}
                  onClick={() => setEditing(true)}
                >
                  {t("actions.edit", "Edit Profile")}
                </Button>
              ) : (
                <Box sx={{ display: "flex", gap: 1 }}>
                  <Button startIcon={<CancelIcon />} onClick={handleCancel}>
                    {t("common.cancel", "Cancel")}
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<SaveIcon />}
                    onClick={handleSave}
                  >
                    {t("common.save", "Save Changes")}
                  </Button>
                </Box>
              )}
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={12} sx={{ mb: 2 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <Avatar
                    sx={{
                      width: 80,
                      height: 80,
                      bgcolor: theme.palette.primary.main,
                    }}
                  >
                    {profileData.firstName[0]}
                    {profileData.lastName[0]}
                  </Avatar>
                  <Box>
                    <Typography variant="h6">
                      {profileData.firstName} {profileData.lastName}
                    </Typography>
                    <Typography color="text.secondary">
                      {profileData.jobTitle}
                    </Typography>
                    {editing && (
                      <Button
                        size="small"
                        startIcon={<PhotoCameraIcon />}
                        sx={{ mt: 1 }}
                      >
                        {t("profile.changePhoto", "Change Photo")}
                      </Button>
                    )}
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label={t("users.form.fields.given_name.label", "First Name")}
                  value={profileData.firstName}
                  disabled={!editing}
                  onChange={(e) =>
                    setProfileData({
                      ...profileData,
                      firstName: e.target.value,
                    })
                  }
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label={t("users.form.fields.family_name.label", "Last Name")}
                  value={profileData.lastName}
                  disabled={!editing}
                  onChange={(e) =>
                    setProfileData({
                      ...profileData,
                      lastName: e.target.value,
                    })
                  }
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label={t("users.form.fields.email.label", "Email")}
                  value={profileData.email}
                  disabled={!editing}
                  type="email"
                  onChange={(e) =>
                    setProfileData({
                      ...profileData,
                      email: e.target.value,
                    })
                  }
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label={t("profile.jobTitle", "Job Title")}
                  value={profileData.jobTitle}
                  disabled={!editing}
                  onChange={(e) =>
                    setProfileData({
                      ...profileData,
                      jobTitle: e.target.value,
                    })
                  }
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label={t("profile.organization", "Organization")}
                  value={profileData.organization}
                  disabled={!editing}
                  onChange={(e) =>
                    setProfileData({
                      ...profileData,
                      organization: e.target.value,
                    })
                  }
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Preferences */}
        <Grid item xs={12} md={4}>
          <Paper
            elevation={0}
            sx={{
              p: 3,
              borderRadius: "12px",
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography variant="h6" sx={{ mb: 3 }}>
              {t("profile.preferences", "Preferences")}
            </Typography>

            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <ScheduleIcon sx={{ mr: 1, color: "text.secondary" }} />
                <Typography variant="subtitle1">
                  {t("profile.timezone", "Timezone")}
                </Typography>
              </Box>
              <FormControl fullWidth>
                <Select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  sx={{ mb: 2 }}
                >
                  {COMMON_TIMEZONES.map((tz) => (
                    <MenuItem key={tz} value={tz}>
                      {formatTimezone(tz)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <NotificationsIcon sx={{ mr: 1, color: "text.secondary" }} />
                <Typography variant="subtitle1">
                  {t("common.notifications", "Notifications")}
                </Typography>
              </Box>
              <FormControlLabel
                control={
                  <Switch
                    checked={profileData.notifications.email}
                    onChange={(e) =>
                      setProfileData({
                        ...profileData,
                        notifications: {
                          ...profileData.notifications,
                          email: e.target.checked,
                        },
                      })
                    }
                  />
                }
                label={t("profile.emailNotifications", "Email Notifications")}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={profileData.notifications.push}
                    onChange={(e) =>
                      setProfileData({
                        ...profileData,
                        notifications: {
                          ...profileData.notifications,
                          push: e.target.checked,
                        },
                      })
                    }
                  />
                }
                label={t("profile.pushNotifications", "Push Notifications")}
              />
            </Box>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <SecurityIcon sx={{ mr: 1, color: "text.secondary" }} />
                <Typography variant="subtitle1">
                  {t("settings.systemSettings.tabs.security", "Security")}
                </Typography>
              </Box>
              <Button variant="outlined" fullWidth sx={{ mb: 1 }}>
                {t("profile.changePassword", "Change Password")}
              </Button>
              <Button variant="outlined" fullWidth>
                {t("profile.twoFactorAuth", "Two-Factor Authentication")}
              </Button>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Box>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <PaletteIcon sx={{ mr: 1, color: "text.secondary" }} />
                <Typography variant="subtitle1">
                  {t("profile.appearance", "Appearance")}
                </Typography>
              </Box>
              <FormControlLabel
                control={
                  <Switch
                    checked={profileData.theme === "dark"}
                    onChange={(e) =>
                      setProfileData({
                        ...profileData,
                        theme: e.target.checked ? "dark" : "light",
                      })
                    }
                  />
                }
                label={t("common.darkMode", "Dark Mode")}
              />
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default UserProfile;
