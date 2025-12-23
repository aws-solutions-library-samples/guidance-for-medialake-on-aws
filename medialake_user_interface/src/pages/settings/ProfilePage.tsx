import React from "react";
import {
  Box,
  Paper,
  Typography,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  useTheme,
  Chip,
  CircularProgress,
  FormControl,
  Select,
  MenuItem,
  SelectChangeEvent,
} from "@mui/material";
import { UserAvatar } from "../../components/common/UserAvatar";
import {
  Email as EmailIcon,
  Person as PersonIcon,
  Language as LanguageIcon,
} from "@mui/icons-material";
import { useGetUser } from "../../api/hooks/useUsers";
import { getCurrentUser } from "aws-amplify/auth";
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { useDirection } from "../../contexts/DirectionContext";

const ProfilePage: React.FC = () => {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const [userId, setUserId] = useState<string | null>(null);
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  // Create a theme with the appropriate direction
  const rtlTheme = useMemo(
    () =>
      createTheme({
        ...theme,
        direction,
      }),
    [theme, direction]
  );

  // Load saved language preference when component mounts
  useEffect(() => {
    // Try to get the language from localStorage with different possible keys
    const savedLanguage =
      localStorage.getItem("userLanguage") ||
      localStorage.getItem("i18nextLng") ||
      localStorage.getItem("i18next");

    if (savedLanguage) {
      console.log("Loading saved language:", savedLanguage);
      i18n.changeLanguage(savedLanguage);
    }
  }, [i18n]);

  useEffect(() => {
    const getCurrentAuthUser = async () => {
      try {
        const { username } = await getCurrentUser();
        setUserId(username);
      } catch (error) {
        console.error(t("errors.loadFailed", "Error getting current user:"), error);
      }
    };
    getCurrentAuthUser();
  }, [t]);

  const { data: userProfile, isLoading, error } = useGetUser(userId || "");

  // Debug logging to see the actual structure of userProfile
  console.log("User Profile Data Structure:", JSON.stringify(userProfile, null, 2));

  if (isLoading) {
    return (
      <ThemeProvider theme={rtlTheme}>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="400px"
          sx={{ direction }}
        >
          <CircularProgress />
        </Box>
      </ThemeProvider>
    );
  }

  if (error) {
    return (
      <ThemeProvider theme={rtlTheme}>
        <Box sx={{ direction }}>
          <Typography color="error">
            {t("errors.loadFailed", "Error loading profile")}: {error.message}
          </Typography>
        </Box>
      </ThemeProvider>
    );
  }

  if (!userProfile) {
    return (
      <ThemeProvider theme={rtlTheme}>
        <Box sx={{ direction }}>
          <Typography>{t("common.error", "No profile data available")}</Typography>
        </Box>
      </ThemeProvider>
    );
  }

  const unavailable = t("common.error", "Unavailable");
  const email = userProfile.data?.attributes?.email || unavailable;
  const firstName = userProfile.data?.attributes?.given_name || "";
  const lastName = userProfile.data?.attributes?.family_name || "";
  const userStatus = userProfile.data?.user_status || unavailable;

  // Messages for missing name fields
  const noFirstNameMsg = t("profile.noFirstName", "User doesn't have a first name configured");
  const noLastNameMsg = t("profile.noLastName", "User doesn't have a last name configured");

  return (
    <ThemeProvider theme={rtlTheme}>
      <Box sx={{ direction }}>
        <Box sx={{ mb: 4 }}>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              mb: 1,
              color: theme.palette.primary.main,
            }}
          >
            {t("profile.title", "Profile")}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {t("profile.description", "Manage your account settings and preferences")}
          </Typography>
        </Box>

        <Grid container spacing={3}>
          {/* Profile Overview */}
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 3, textAlign: "center" }}>
              <UserAvatar
                size={120}
                fontSize="3rem"
                sx={{
                  margin: "0 auto 16px",
                }}
              />
              {(firstName || lastName) && (
                <Typography
                  variant="h5"
                  gutterBottom
                  sx={{ textAlign: isRTL ? "center" : "center" }}
                >
                  {`${firstName} ${lastName}`.trim()}
                </Typography>
              )}
              <Typography
                variant="body2"
                color="text.secondary"
                gutterBottom
                sx={{ textAlign: isRTL ? "center" : "center" }}
              >
                {email}
              </Typography>
              <Chip label={userStatus} color="success" size="small" sx={{ mt: 1 }} />
            </Paper>
          </Grid>

          {/* Profile Details */}
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom sx={{ textAlign: isRTL ? "right" : "left" }}>
                {t("profile.title", "Profile")}
              </Typography>
              <List sx={{ textAlign: isRTL ? "right" : "left" }}>
                <ListItem>
                  <ListItemIcon>
                    <EmailIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("users.form.fields.email.label", "Email")}
                    secondary={email}
                    primaryTypographyProps={{ align: isRTL ? "right" : "left" }}
                    secondaryTypographyProps={{
                      align: isRTL ? "right" : "left",
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <PersonIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("users.form.fields.given_name.label", "First Name")}
                    secondary={firstName ? firstName : noFirstNameMsg}
                    primaryTypographyProps={{ align: isRTL ? "right" : "left" }}
                    secondaryTypographyProps={{
                      align: isRTL ? "right" : "left",
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <PersonIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("users.form.fields.family_name.label", "Last Name")}
                    secondary={lastName ? lastName : noLastNameMsg}
                    primaryTypographyProps={{ align: isRTL ? "right" : "left" }}
                    secondaryTypographyProps={{
                      align: isRTL ? "right" : "left",
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <LanguageIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("common.language", "Language")}
                    primaryTypographyProps={{ align: isRTL ? "right" : "left" }}
                    secondary={
                      <FormControl
                        variant="outlined"
                        size="small"
                        sx={{
                          mt: 1,
                          minWidth: 200,
                          textAlign: isRTL ? "right" : "left",
                          width: "100%",
                        }}
                      >
                        <Select
                          value={i18n.language}
                          sx={{
                            textAlign: isRTL ? "right" : "left",
                            "& .MuiSelect-select": {
                              textAlign: isRTL ? "right" : "left",
                              paddingRight: isRTL ? "8px" : "32px",
                              paddingLeft: isRTL ? "32px" : "8px",
                            },
                          }}
                          onChange={(e: SelectChangeEvent) => {
                            const newLanguage = e.target.value;
                            console.log("Changing language to:", newLanguage);

                            // Save language in multiple places to ensure it persists
                            localStorage.setItem("userLanguage", newLanguage);
                            localStorage.setItem("i18nextLng", newLanguage);
                            localStorage.setItem("i18next", newLanguage);

                            // Force language change - DirectionContext will handle direction update
                            i18n.changeLanguage(newLanguage);

                            // Log for debugging
                            const isRtlLanguage = ["ar", "he"].includes(newLanguage);
                            console.log(
                              "Language changed to:",
                              newLanguage,
                              "isRTL:",
                              isRtlLanguage
                            );
                          }}
                        >
                          <MenuItem
                            value="en"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.english")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    GB
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    GB
                                  </Box>
                                  <span>{t("languages.english")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="de"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.german")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    DE
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    DE
                                  </Box>
                                  <span>{t("languages.german")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="pt"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.portuguese")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    PT
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    PT
                                  </Box>
                                  <span>{t("languages.portuguese")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="fr"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.french")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    FR
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    FR
                                  </Box>
                                  <span>{t("languages.french")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="zh"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.chinese")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    CN
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    CN
                                  </Box>
                                  <span>{t("languages.chinese")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="hi"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.hindi")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    IN
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    IN
                                  </Box>
                                  <span>{t("languages.hindi")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="ar"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.arabic")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    SA
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    SA
                                  </Box>
                                  <span>{t("languages.arabic")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                          <MenuItem
                            value="he"
                            sx={{
                              textAlign: isRTL ? "right" : "left",
                              justifyContent: isRTL ? "flex-end" : "flex-start",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: isRTL ? "row-reverse" : "row",
                                alignItems: "center",
                                gap: "8px",
                                width: "100%",
                                justifyContent: isRTL ? "flex-end" : "flex-start",
                              }}
                            >
                              {isRTL ? (
                                <>
                                  <span>{t("languages.hebrew")}</span>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    IL
                                  </Box>
                                </>
                              ) : (
                                <>
                                  <Box
                                    sx={{
                                      width: 24,
                                      height: 16,
                                      border: "1px solid #ccc",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontSize: "10px",
                                    }}
                                  >
                                    IL
                                  </Box>
                                  <span>{t("languages.hebrew")}</span>
                                </>
                              )}
                            </Box>
                          </MenuItem>
                        </Select>
                      </FormControl>
                    }
                  />
                </ListItem>
              </List>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </ThemeProvider>
  );
};

export default ProfilePage;
