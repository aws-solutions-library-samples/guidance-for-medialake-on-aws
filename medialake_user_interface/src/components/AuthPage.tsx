import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import {
  Box,
  CircularProgress,
  Button,
  Typography,
  Stack,
  Divider,
  TextField,
  Alert,
  Link,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { Terrain as LogoIcon } from "@mui/icons-material";
import { Authenticator, ThemeProvider as AmplifyThemeProvider } from "@aws-amplify/ui-react";
import {
  fetchAuthSession,
  signIn,
  confirmSignIn,
  signInWithRedirect,
  resetPassword,
  confirmResetPassword,
} from "aws-amplify/auth";
import { useAuth } from "../common/hooks/auth-context";
import { useAwsConfig } from "../common/hooks/aws-config-context";
import { StorageHelper } from "../common/helpers/storage-helper";
import { theme, components } from "./auth/theme";
import { colorTokens } from "../theme/tokens";
import { useTranslation } from "react-i18next";

type ForgotPasswordStep = "idle" | "enterEmail" | "enterCode" | "success";

const inputSx = {
  "& .MuiOutlinedInput-root": {
    backgroundColor: "rgba(255, 255, 255, 0.1)",
    color: "white",
    height: "40px",
    "& fieldset": { borderColor: "rgba(255, 255, 255, 0.2)" },
    "&:hover fieldset": { borderColor: "rgba(255, 255, 255, 0.4)" },
    "&.Mui-focused fieldset": { borderColor: "rgba(255, 255, 255, 0.5)" },
  },
  "& .MuiInputBase-input": {
    color: "white",
    textAlign: "center",
    "&::placeholder": { color: "rgba(255, 255, 255, 0.5)" },
  },
  "& .MuiInputLabel-root": { color: "rgba(255, 255, 255, 0.7)" },
};

const AuthPage = () => {
  const { completeLogin, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const awsConfig = useAwsConfig();
  const { t } = useTranslation();

  // Forgot password state
  const [forgotPasswordStep, setForgotPasswordStep] = useState<ForgotPasswordStep>("idle");
  const [fpEmail, setFpEmail] = useState("");
  const [fpCode, setFpCode] = useState("");
  const [fpNewPassword, setFpNewPassword] = useState("");
  const [fpConfirmPassword, setFpConfirmPassword] = useState("");
  const [fpError, setFpError] = useState("");
  const [fpLoading, setFpLoading] = useState(false);

  // Deep-link: auto-open forgot password form when ?action=reset-password
  useEffect(() => {
    if (searchParams.get("action") === "reset-password") {
      setForgotPasswordStep("enterEmail");
    }
  }, [searchParams]);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/");
    }
  }, [isAuthenticated, navigate]);

  if (!awsConfig) {
    return <CircularProgress />;
  }

  const hasSamlProvider = awsConfig.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "saml"
  );
  const hasCognitoProvider = awsConfig.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "cognito"
  );

  const handleSendResetCode = async () => {
    setFpError("");
    setFpLoading(true);
    try {
      await resetPassword({ username: fpEmail });
      setForgotPasswordStep("enterCode");
    } catch (error: any) {
      setFpError(t("auth.forgotPassword.errorSendingCode"));
    } finally {
      setFpLoading(false);
    }
  };

  const handleConfirmReset = async () => {
    setFpError("");
    if (fpNewPassword !== fpConfirmPassword) {
      setFpError(t("auth.forgotPassword.passwordMismatch"));
      return;
    }
    setFpLoading(true);
    try {
      await confirmResetPassword({
        username: fpEmail,
        confirmationCode: fpCode,
        newPassword: fpNewPassword,
      });
      setForgotPasswordStep("success");
    } catch (error: any) {
      setFpError(t("auth.forgotPassword.errorResettingPassword"));
    } finally {
      setFpLoading(false);
    }
  };

  const handleBackToSignIn = () => {
    setForgotPasswordStep("idle");
    setFpEmail("");
    setFpCode("");
    setFpNewPassword("");
    setFpConfirmPassword("");
    setFpError("");
  };

  const renderForgotPasswordFlow = () => {
    if (forgotPasswordStep === "enterEmail") {
      return (
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography
            sx={{ color: "rgba(255, 255, 255, 0.9)", fontSize: "1.1rem", fontWeight: 600 }}
          >
            {t("auth.forgotPassword.title")}
          </Typography>
          <Typography sx={{ color: "rgba(255, 255, 255, 0.7)", fontSize: "0.85rem" }}>
            {t("auth.forgotPassword.description")}
          </Typography>
          {fpError && (
            <Alert severity="error" sx={{ fontSize: "0.8rem" }}>
              {fpError}
            </Alert>
          )}
          <TextField
            fullWidth
            size="small"
            placeholder={t("auth.forgotPassword.emailPlaceholder")}
            value={fpEmail}
            onChange={(e) => setFpEmail(e.target.value)}
            sx={inputSx}
          />
          <Button
            fullWidth
            onClick={handleSendResetCode}
            disabled={!fpEmail || fpLoading}
            sx={{
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              color: "white",
              height: "40px",
              textTransform: "none",
              "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.3)" },
              "&.Mui-disabled": { color: "rgba(255, 255, 255, 0.4)" },
            }}
          >
            {fpLoading ? (
              <CircularProgress size={20} sx={{ color: "white" }} />
            ) : (
              t("auth.forgotPassword.sendCode")
            )}
          </Button>
          <Link
            component="button"
            onClick={handleBackToSignIn}
            sx={{
              color: "rgba(255, 255, 255, 0.7)",
              fontSize: "0.85rem",
              textDecoration: "underline",
            }}
          >
            {t("auth.forgotPassword.backToSignIn")}
          </Link>
        </Stack>
      );
    }

    if (forgotPasswordStep === "enterCode") {
      return (
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography
            sx={{ color: "rgba(255, 255, 255, 0.9)", fontSize: "1.1rem", fontWeight: 600 }}
          >
            {t("auth.forgotPassword.title")}
          </Typography>
          <Typography sx={{ color: "rgba(255, 255, 255, 0.7)", fontSize: "0.85rem" }}>
            {t("auth.forgotPassword.codeSent")}
          </Typography>
          {fpError && (
            <Alert severity="error" sx={{ fontSize: "0.8rem" }}>
              {fpError}
            </Alert>
          )}
          <TextField
            fullWidth
            size="small"
            placeholder={t("auth.forgotPassword.codePlaceholder")}
            value={fpCode}
            onChange={(e) => setFpCode(e.target.value)}
            sx={inputSx}
          />
          <TextField
            fullWidth
            size="small"
            type="password"
            placeholder={t("auth.forgotPassword.newPasswordPlaceholder")}
            value={fpNewPassword}
            onChange={(e) => setFpNewPassword(e.target.value)}
            sx={inputSx}
          />
          <TextField
            fullWidth
            size="small"
            type="password"
            placeholder={t("auth.forgotPassword.confirmPasswordPlaceholder")}
            value={fpConfirmPassword}
            onChange={(e) => setFpConfirmPassword(e.target.value)}
            sx={inputSx}
          />
          <Button
            fullWidth
            onClick={handleConfirmReset}
            disabled={!fpCode || !fpNewPassword || !fpConfirmPassword || fpLoading}
            sx={{
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              color: "white",
              height: "40px",
              textTransform: "none",
              "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.3)" },
              "&.Mui-disabled": { color: "rgba(255, 255, 255, 0.4)" },
            }}
          >
            {fpLoading ? (
              <CircularProgress size={20} sx={{ color: "white" }} />
            ) : (
              t("auth.forgotPassword.resetPassword")
            )}
          </Button>
          <Link
            component="button"
            onClick={handleBackToSignIn}
            sx={{
              color: "rgba(255, 255, 255, 0.7)",
              fontSize: "0.85rem",
              textDecoration: "underline",
            }}
          >
            {t("auth.forgotPassword.backToSignIn")}
          </Link>
        </Stack>
      );
    }

    if (forgotPasswordStep === "success") {
      return (
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Alert severity="success" sx={{ fontSize: "0.85rem" }}>
            {t("auth.forgotPassword.success")}
          </Alert>
          <Button
            fullWidth
            onClick={handleBackToSignIn}
            sx={{
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              color: "white",
              height: "40px",
              textTransform: "none",
              "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.3)" },
            }}
          >
            {t("auth.forgotPassword.backToSignIn")}
          </Button>
        </Stack>
      );
    }

    return null;
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        bgcolor: "background.default",
        backgroundImage: `linear-gradient(135deg, ${
          colorTokens.background.default.light
        } 0%, ${alpha(colorTokens.primary.main, 0.08)} 100%)`,
        padding: "20px",
        gap: "20px",
      }}
    >
      <Box
        sx={{
          background: `linear-gradient(135deg, ${colorTokens.primary.main} 0%, ${colorTokens.primary.dark} 100%)`,
          borderRadius: "8px",
          boxShadow: (theme) => `0 4px 12px ${alpha(theme.palette.common.black, 0.15)}`,
          padding: "2.5rem",
          textAlign: "center",
          color: "white",
          width: "400px",
        }}
      >
        <Box sx={{ mb: 4 }}>
          <LogoIcon
            sx={{
              fontSize: "40px",
              color: "white",
              mb: 2,
            }}
          />
          <h1
            style={{
              fontSize: "1.5rem",
              fontWeight: "600",
              margin: "0 0 0.5rem",
            }}
          >
            Welcome to Media Lake
          </h1>
          <p
            style={{
              fontSize: "0.875rem",
              color: "rgba(255, 255, 255, 0.85)",
              margin: "0",
              lineHeight: "1.5",
            }}
          >
            A data lake for your media, metadata, and media pipelines.
          </p>
        </Box>

        <Stack spacing={2} sx={{ mt: 2 }}>
          {hasSamlProvider &&
            awsConfig.Auth.identity_providers.map((provider) => {
              if (provider.identity_provider_method === "saml") {
                return (
                  <Button
                    key={provider.identity_provider_name}
                    onClick={() => {
                      signInWithRedirect({
                        provider: { custom: provider.identity_provider_name },
                      }).catch((error) => {
                        console.error("SAML redirect error:", error);
                      });
                    }}
                    sx={{
                      padding: "12px 24px",
                      fontSize: "1rem",
                      backgroundColor: "rgba(255, 255, 255, 0.2)",
                      color: "white",
                      height: "40px",
                      width: "100%",
                      textTransform: "none",
                      "&:hover": {
                        backgroundColor: "rgba(255, 255, 255, 0.3)",
                      },
                    }}
                  >
                    Sign in with {provider.identity_provider_name}
                  </Button>
                );
              }
              return null;
            })}

          {hasSamlProvider && hasCognitoProvider && (
            <Divider sx={{ my: 2, borderColor: "rgba(255, 255, 255, 0.2)" }}>
              <Typography sx={{ color: "rgba(255, 255, 255, 0.7)" }}>OR</Typography>
            </Divider>
          )}

          {hasCognitoProvider && forgotPasswordStep !== "idle" && renderForgotPasswordFlow()}

          {hasCognitoProvider && forgotPasswordStep === "idle" && (
            <>
              <Box
                sx={{
                  "& [data-amplify-router]": {
                    background: "transparent !important",
                    boxShadow: "none !important",
                    maxWidth: "none !important",
                    width: "100% !important",
                    border: "none !important",
                  },
                  "& .amplify-authenticator": {
                    marginBottom: "1rem",
                    maxWidth: "none",
                    width: "100%",
                  },
                  "& [data-amplify-authenticator]": {
                    backgroundColor: "transparent !important",
                    border: "none !important",
                  },
                  "& [data-amplify-container]": {
                    padding: "0",
                    maxWidth: "none",
                    width: "100%",
                  },
                  "& [data-amplify-form]": {
                    padding: "0",
                    maxWidth: "none",
                    width: "100%",
                  },
                  '& .amplify-button[type="submit"]': {
                    maxWidth: "none",
                    width: "100%",
                  },
                  "& .amplify-divider, & .amplify-divider--small": {
                    display: "none",
                  },
                  "& .amplify-tabs": {
                    width: "100%",
                  },
                  "& .amplify-button": {
                    backgroundColor: "rgba(255, 255, 255, 0.2)",
                    color: "white",
                    height: "40px",
                    width: "100%",
                    "&:hover": {
                      backgroundColor: "rgba(255, 255, 255, 0.3)",
                    },
                  },
                  "& .amplify-field": {
                    "--amplify-components-field-label-color": "rgba(255, 255, 255, 0.9)",
                    width: "100%",
                    "& .amplify-flex": {
                      width: "100%",
                    },
                  },
                  "& .amplify-input": {
                    width: "100%",
                    height: "40px",
                    borderColor: "rgba(255, 255, 255, 0.2)",
                    "&:focus": {
                      borderColor: "rgba(255, 255, 255, 0.5)",
                      backgroundColor: "rgba(255, 255, 255, 0.15)",
                    },
                    "&::placeholder": {
                      color: "rgba(255, 255, 255, 0.5)",
                    },
                  },
                  '& [name="username"]': {
                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                    color: "white",
                    textAlign: "center",
                  },
                  '& [name="password"]': {
                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                    color: "white",
                    width: "calc(100%)",
                    textAlign: "center",
                    paddingLeft: "50px",
                  },
                  '& [name="confirm_password"]': {
                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                    color: "white",
                    textAlign: "center",
                    paddingLeft: "50px",
                  },
                  "& .amplify-text": {
                    color: "rgba(255, 255, 255, 0.9)",
                  },
                  "& .amplify-label": {
                    color: "rgba(255, 255, 255, 0.9)",
                  },
                  "& .amplify-heading": {
                    color: "rgba(255, 255, 255, 0.9)",
                  },
                }}
              >
                <AmplifyThemeProvider theme={theme}>
                  <Authenticator
                    loginMechanisms={["email"]}
                    signUpAttributes={["email"]}
                    hideSignUp={true}
                    components={components}
                    formFields={{
                      forceNewPassword: {
                        password: {
                          placeholder: "Enter your Password",
                        },
                        confirm_password: {
                          placeholder: "Confirm Password",
                        },
                      },
                      signIn: {
                        username: {
                          placeholder: "Enter your email",
                        },
                        password: {
                          placeholder: "Enter your Password",
                        },
                      },
                    }}
                    services={{
                      async handleSignIn(input) {
                        try {
                          const signInResult = await signIn(input);

                          if (
                            signInResult.nextStep.signInStep ===
                            "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"
                          ) {
                            return {
                              isSignedIn: false,
                              nextStep: {
                                signInStep: "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED",
                              },
                            };
                          }

                          const session = await fetchAuthSession();
                          const token = session.tokens?.idToken?.toString();

                          if (token) {
                            StorageHelper.setToken(token);
                            completeLogin();
                            navigate("/");
                          }

                          return {
                            isSignedIn: true,
                            nextStep: {
                              signInStep: "DONE",
                            },
                          };
                        } catch (error) {
                          console.error("Error during sign in:", error);
                          throw error;
                        }
                      },
                      async handleConfirmSignIn(input) {
                        try {
                          await confirmSignIn(input);

                          const session = await fetchAuthSession();
                          const token = session.tokens?.idToken?.toString();

                          if (token) {
                            StorageHelper.setToken(token);
                            completeLogin();
                            navigate("/");
                          }

                          return {
                            isSignedIn: true,
                            nextStep: {
                              signInStep: "DONE",
                            },
                          };
                        } catch (error) {
                          console.error("Error during confirm sign in:", error);
                          throw error;
                        }
                      },
                    }}
                  />
                </AmplifyThemeProvider>
              </Box>
              <Link
                component="button"
                onClick={() => setForgotPasswordStep("enterEmail")}
                sx={{
                  color: "rgba(255, 255, 255, 0.7)",
                  fontSize: "0.85rem",
                  textDecoration: "underline",
                  cursor: "pointer",
                  "&:hover": { color: "rgba(255, 255, 255, 0.9)" },
                }}
              >
                {t("auth.forgotPassword.link")}
              </Link>
            </>
          )}
        </Stack>
      </Box>
    </Box>
  );
};

export default AuthPage;
