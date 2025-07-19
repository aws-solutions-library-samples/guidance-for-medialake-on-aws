import React, { Suspense, useState, useEffect } from "react";
import ReactDOM from "react-dom/client";
import AppConfigured from "./components/app-configured";
import { Amplify } from "aws-amplify";
import { useTranslation } from "react-i18next";
import { FeatureFlagsProvider } from "./contexts/FeatureFlagsContext";

// Import and initialize i18next configuration
import "./i18n/i18n";

// Create a loading component that uses translations
const LoadingFallback = () => {
  const { t } = useTranslation();
  return <>{t("app.loading", "Loading...")}</>;
};

// App component that initializes feature flags and renders AppConfigured
const App = () => {
  const [isLoading, setIsLoading] = useState(true);
  const { t } = useTranslation();

  useEffect(() => {
    // Initialize AWS configuration
    const initializeApp = async () => {
      try {
        await initializeAWS();
        setIsLoading(false);
      } catch (error) {
        console.error(
          t("app.errors.loadingConfig", "Error loading configuration:"),
          error,
        );
        setIsLoading(false);
      }
    };

    const initializeAWS = async () => {
      try {
        // Fetch AWS configuration
        const awsResponse = await fetch("/aws-exports.json");
        const awsConfig = await awsResponse.json();

        // Configure Amplify
        Amplify.configure({
          Auth: {
            Cognito: {
              userPoolId: awsConfig.Auth.Cognito.userPoolId,
              userPoolClientId: awsConfig.Auth.Cognito.userPoolClientId,
              identityPoolId: awsConfig.Auth.Cognito.identityPoolId,
            },
          },
          API: awsConfig.API,
        });

        return true;
      } catch (error) {
        console.error("Error loading AWS configuration:", error);
        throw error;
      }
    };

    initializeApp();
  }, [t]);

  if (isLoading) {
    return <LoadingFallback />;
  }

  return (
    <FeatureFlagsProvider>
      <Suspense fallback={<LoadingFallback />}>
        <AppConfigured />
      </Suspense>
    </FeatureFlagsProvider>
  );
};

// Render the app
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
