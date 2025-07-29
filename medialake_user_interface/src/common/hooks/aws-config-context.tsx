import React, {
  createContext,
  useState,
  useEffect,
  useContext,
  ReactNode,
} from "react";
import { StorageHelper } from "../helpers/storage-helper";
import { Amplify } from "aws-amplify";

interface IdentityProvider {
  identity_provider_method: "cognito" | "saml";
  identity_provider_name?: string;
  identity_provider_metadata_url?: string;
  identity_provider_metadata_path?: string;
}

interface AwsConfig {
  Auth: {
    identity_providers: IdentityProvider[];
    Cognito: {
      userPoolId: string;
      userPoolClientId: string;
      identityPoolId: string;
      domain: string;
    };
  };
  API: any;
}

export const AwsConfigContext = createContext<AwsConfig | null>(null);

interface AwsConfigProviderProps {
  children: ReactNode;
}

const configureAmplify = (config: AwsConfig) => {
  const amplifyConfig: any = {
    Auth: {
      Cognito: {
        userPoolId: config.Auth.Cognito.userPoolId,
        userPoolClientId: config.Auth.Cognito.userPoolClientId,
        identityPoolId: config.Auth.Cognito.identityPoolId,
        loginWith: {
          username: false,
          email: false,
          oauth: {
            domain: config.Auth.Cognito.domain,
            scopes: ["email", "openid", "profile"],
            responseType: "code",
            redirectSignIn: window.location.origin,
            redirectSignOut: window.location.origin + "/sign-in",
          },
        },
      },
    },
    API: config.API,
  };

  // Configure login methods based on identity providers
  const hasCognito = config.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "cognito",
  );
  const samlProviders = config.Auth.identity_providers.filter(
    (provider) => provider.identity_provider_method === "saml",
  );

  // Enable username/password login if Cognito is configured
  if (hasCognito) {
    amplifyConfig.Auth.Cognito.loginWith.username = true;
    amplifyConfig.Auth.Cognito.loginWith.email = true;
  }

  // Add SAML configuration if any SAML providers are configured
  if (samlProviders.length > 0) {
    console.log(
      "Configuring SAML providers:",
      samlProviders.map((p) => p.identity_provider_name),
    );
    amplifyConfig.Auth.Cognito.loginWith.oauth = {
      ...amplifyConfig.Auth.Cognito.loginWith.oauth,
      providers: ["SAML"],
      redirectSignIn: [
        window.location.origin,
        window.location.origin + "/",
        window.location.origin + "/sign-in",
        `https://${config.Auth.Cognito.domain}/oauth2/idpresponse`,
        `https://${config.Auth.Cognito.domain}/saml2/idpresponse`,
      ],
      redirectSignOut: [
        window.location.origin,
        window.location.origin + "/",
        window.location.origin + "/sign-in",
      ],
    };
  }

  Amplify.configure(amplifyConfig);
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
        .then((response) => response.json())
        .then((data) => {
          configureAmplify(data);
          StorageHelper.setAwsConfig(data);
          setAwsConfig(data);
          setIsLoading(false);
        })
        .catch((error) => {
          console.error("Error fetching AWS config:", error);
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
    throw new Error("useAwsConfig must be used within an AwsConfigProvider");
  }
  return context;
};
