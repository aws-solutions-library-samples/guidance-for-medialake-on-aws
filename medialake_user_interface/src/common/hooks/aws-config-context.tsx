import React, { createContext, useState, useEffect, ReactNode } from 'react';
import { StorageHelper } from '../helpers/storage-helper';

export const AwsConfigContext = createContext<any>(null);

interface AwsConfigProviderProps {
  children: ReactNode;
}

export const AwsConfigProvider: React.FC<AwsConfigProviderProps> = ({ children }) => {
  const [awsConfig, setAwsConfig] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedConfig = StorageHelper.getAwsConfig();
    if (storedConfig) {
      setAwsConfig(storedConfig);
      setIsLoading(false);
    } else {
      fetch("/aws-exports.json")
        .then(response => response.json())
        .then(data => {
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