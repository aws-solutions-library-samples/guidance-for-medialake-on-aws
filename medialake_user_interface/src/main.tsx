import React from 'react';
import ReactDOM from 'react-dom/client';
import AppConfigured from "./components/app-configured";
import { Amplify } from 'aws-amplify';

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

    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <AppConfigured />
      </React.StrictMode>
    )
  })
  .catch(error => {
    console.error('Error loading AWS configuration:', error);
  });
