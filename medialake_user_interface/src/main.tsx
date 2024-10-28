import React from 'react'
import ReactDOM from 'react-dom/client'
import AppConfigured from "./components/app-configured";
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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

    // Create a client
    const queryClient = new QueryClient()

    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <AppConfigured />
        </QueryClientProvider>
      </React.StrictMode>
    )
  })
  .catch(error => {
    console.error('Error loading AWS configuration:', error);
  });
