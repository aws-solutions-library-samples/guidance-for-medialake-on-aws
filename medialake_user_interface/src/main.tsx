import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import AppConfigured from './components/app-configured';
import { Amplify } from 'aws-amplify';
import { useTranslation } from 'react-i18next';

// Import and initialize i18next configuration
import './i18n/i18n';

// Create a loading component that uses translations
const LoadingFallback = () => {
  const { t } = useTranslation();
  return <>{t('app.loading', 'Loading...')}</>;
};

// Initialize Amplify with the configuration from aws-exports.json
fetch('/aws-exports.json')
  .then(response => response.json())
  .then(awsConfig => {
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: awsConfig.Auth.Cognito.userPoolId,
          userPoolClientId: awsConfig.Auth.Cognito.userPoolClientId,
          identityPoolId: awsConfig.Auth.Cognito.identityPoolId,
        }
      },
      API: awsConfig.API
    });

    ReactDOM.createRoot(document.getElementById('root')).render(

        <Suspense fallback={<LoadingFallback />}>
          <AppConfigured />
        </Suspense>

    )
  })
  .catch(error => {
    console.error(useTranslation().t('app.errors.loadingConfig', 'Error loading AWS configuration:'), error);
  });
