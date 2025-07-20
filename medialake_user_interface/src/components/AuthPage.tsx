import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  CircularProgress,
  Button,
  Typography,
  Stack,
  Divider,
} from "@mui/material";
import { Terrain as LogoIcon } from "@mui/icons-material";
import {
  Authenticator,
  ThemeProvider as AmplifyThemeProvider,
} from "@aws-amplify/ui-react";
import {
  fetchAuthSession,
  signIn,
  confirmSignIn,
  signInWithRedirect,
} from "aws-amplify/auth";
import { useAuth } from "../common/hooks/auth-context";
import { useAwsConfig } from "../common/hooks/aws-config-context";
import { StorageHelper } from "../common/helpers/storage-helper";
import { theme, components } from "./auth/theme";

const AuthPage = () => {
  const { setIsAuthenticated, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const awsConfig = useAwsConfig();

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/");
    }
  }, [isAuthenticated, navigate]);

  if (!awsConfig) {
    return <CircularProgress />;
  }

  const hasSamlProvider = awsConfig.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "saml",
  );
  const hasCognitoProvider = awsConfig.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "cognito",
  );

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        bgcolor: "#f0f2f5",
        backgroundImage: "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
        padding: "20px",
        gap: "20px",
      }}
    >
      <Box
        sx={{
          background: "linear-gradient(135deg, #0050b3 0%, #002766 100%)",
          borderRadius: "8px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
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
                      console.log(
                        "Initiating SAML login with provider:",
                        provider.identity_provider_name,
                      );
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
              <Typography sx={{ color: "rgba(255, 255, 255, 0.7)" }}>
                OR
              </Typography>
            </Divider>
          )}

          {hasCognitoProvider && (
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
                  "--amplify-components-field-label-color":
                    "rgba(255, 255, 255, 0.9)",
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
                  // marginLeft: '-50px',
                  // paddingRight: '40px',
                  paddingLeft: "50px", // Padding only applies to placeholder text
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
                              signInStep:
                                "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED",
                            },
                          };
                        }

                        const session = await fetchAuthSession();
                        const token = session.tokens?.idToken?.toString();

                        if (token) {
                          StorageHelper.setToken(token);
                          setIsAuthenticated(true);
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
                        const confirmResult = await confirmSignIn(input);

                        const session = await fetchAuthSession();
                        const token = session.tokens?.idToken?.toString();

                        if (token) {
                          StorageHelper.setToken(token);
                          setIsAuthenticated(true);
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
          )}
        </Stack>
      </Box>
    </Box>
  );
};

export default AuthPage;
