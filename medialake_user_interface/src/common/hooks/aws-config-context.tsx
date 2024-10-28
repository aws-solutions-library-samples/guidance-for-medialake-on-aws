import React, { createContext, useState, useEffect, useContext, ReactNode } from 'react';
import { StorageHelper } from '../helpers/storage-helper';
import { Amplify } from 'aws-amplify';

interface AwsConfig {
  Auth: {
    Cognito: {
      userPoolId: string;
      userPoolClientId: string;
      identityPoolId: string;
    };
  };
  API: any;
}

export const AwsConfigContext = createContext<AwsConfig | null>(null);

interface AwsConfigProviderProps {
  children: ReactNode;
}

const configureAmplify = (config: AwsConfig) => {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.Auth.Cognito.userPoolId,
        userPoolClientId: config.Auth.Cognito.userPoolClientId,
        identityPoolId: config.Auth.Cognito.identityPoolId,
      }
    },
    API: config.API
  });
};

export const AwsConfigProvider = ({ children }: AwsConfigProviderProps) => {
  const [awsConfig, setAwsConfig] = useState<AwsConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedConfig = StorageHelper.getAwsConfig();
    if (storedConfig) {
      configureAmplify(storedConfig);
      setAwsConfig(storedConfig);
      setIsLoading(false);
    } else {
      fetch("/aws-exports.json")
        .then(response => response.json())
        .then(data => {
          configureAmplify(data);
          StorageHelper.setAwsConfig(data);
          setAwsConfig(data);
          setIsLoading(false);
        })
        .catch(error => {
          console.error('Error fetching AWS config:', error);
          setIsLoading(false);
        });
    }
  }, []);

  if (isLoading) {
    return <div>Loading AWS configuration...</div>;
  }

  return (
    <AwsConfigContext.Provider value={awsConfig}>
      {children}
    </AwsConfigContext.Provider>
  );
};

export const useAwsConfig = () => {
  const context = useContext(AwsConfigContext);
  if (context === undefined) {
    throw new Error('useAwsConfig must be used within an AwsConfigProvider');
  }
  return context;
};
