import {
  CognitoRefreshToken,
  AuthenticationDetails,
  CognitoUser,
} from "amazon-cognito-identity-js";
import { signInWithRedirect } from "aws-amplify/auth";
import { useUserPool } from "./userpool";
import { StorageHelper } from "../helpers/storage-helper";
import { useAwsConfig } from "./aws-config-context";

export const useAuthenticate = () => {
  const { userPool, reinitializeUserPool } = useUserPool();
  const awsConfig = useAwsConfig();

  const initiateAuth = async (
    Email: string,
    Password: string,
  ): Promise<any> => {
    if (!awsConfig) {
      throw new Error("AWS configuration is not initialized");
    }

    // Find SAML provider if configured
    const samlProvider = awsConfig.Auth.identity_providers.find(
      (provider) => provider.identity_provider_method === "saml",
    );

    // If SAML is configured, redirect to SAML login
    if (samlProvider) {
      try {
        await signInWithRedirect({
          provider: { custom: samlProvider.identity_provider_name || "" },
        });
        return { type: "SAML_REDIRECT" };
      } catch (error) {
        console.error("SAML redirect failed:", error);
        throw error;
      }
    }

    // Otherwise, proceed with Cognito authentication
    return authenticate(Email, Password);
  };

  const authenticate = async (
    Email: string,
    Password: string,
  ): Promise<any> => {
    // This is now an internal method for Cognito authentication
    if (!userPool) {
      reinitializeUserPool();
      throw new Error("User pool is not initialized");
    }

    return new Promise((resolve, reject) => {
      const user = new CognitoUser({
        Username: Email,
        Pool: userPool,
      });

      const authDetails = new AuthenticationDetails({
        Username: Email,
        Password,
      });

      user.authenticateUser(authDetails, {
        onSuccess: (result) => {
          console.log(result);
          StorageHelper.setToken(result.getIdToken().getJwtToken());
          StorageHelper.setUsername(result.getIdToken().payload.email);
          StorageHelper.setRefreshToken(result.getRefreshToken().getToken());
          resolve({ type: "SUCCESS", result });
        },
        newPasswordRequired: (userAttributes) => {
          resolve({ type: "NEW_PASSWORD_REQUIRED", user, userAttributes });
        },
        onFailure: (err) => {
          console.log("login failed", err);
          StorageHelper.clearToken();
          StorageHelper.clearUsername();
          reject({ error: err, user }); // Include the user object in the rejection
        },
      });
    });
  };

  const changePassword = async (
    user: CognitoUser,
    newPassword: string,
    userAttributes: any,
  ): Promise<any> => {
    return new Promise((resolve, reject) => {
      user.completeNewPasswordChallenge(newPassword, userAttributes, {
        onSuccess: (result) => {
          console.log(result);
          StorageHelper.setToken(result.getIdToken().getJwtToken());
          StorageHelper.setUsername(result.getIdToken().payload.email);
          StorageHelper.setRefreshToken(result.getRefreshToken().getToken());
          resolve(result);
        },
        onFailure: (err) => {
          console.log("Change password failed", err);
          reject(err);
        },
      });
    });
  };

  const refreshSession = async (): Promise<any> => {
    if (!userPool) {
      reinitializeUserPool();
      throw new Error("User pool is not initialized");
    }
    return new Promise((resolve, reject) => {
      const user = userPool.getCurrentUser();
      if (!user) {
        reject(new Error("No current user"));
        return;
      }

      const refreshToken = StorageHelper.getRefreshToken();
      if (!refreshToken) {
        reject(new Error("No refresh token available"));
        return;
      }

      const token = new CognitoRefreshToken({ RefreshToken: refreshToken });

      user.refreshSession(token, (err, session) => {
        if (err) {
          console.log("Failed to refresh session:", err);
          reject(err);
        } else {
          console.log("Session refreshed successfully");
          StorageHelper.setToken(session.getIdToken().getJwtToken());
          StorageHelper.setRefreshToken(session.getRefreshToken().getToken());
          resolve(session);
        }
      });
    });
  };

  const logout = async (): Promise<void> => {
    if (!userPool) {
      reinitializeUserPool();
      throw new Error("User pool is not initialized");
    }
    const user = userPool.getCurrentUser();
    if (user) {
      user.signOut();
    }
    StorageHelper.clearToken();
    //window.location.href = '/';
  };

  return { authenticate: initiateAuth, logout, refreshSession, changePassword };
};
