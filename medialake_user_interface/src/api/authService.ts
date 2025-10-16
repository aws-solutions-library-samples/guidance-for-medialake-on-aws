import {
  fetchAuthSession,
  getCurrentUser,
  fetchUserAttributes,
  signInWithRedirect,
  signIn,
} from "aws-amplify/auth";
import { Hub, HubCapsule } from "@aws-amplify/core";
import { StorageHelper } from "../common/helpers/storage-helper";
import PermissionTokenCache from "../permissions/utils/permission-token-cache";

class AuthService {
  constructor() {
    // Listen for auth events
    Hub.listen(
      "auth",
      async (capsule: HubCapsule<"auth", { event: string }>) => {
        const { payload } = capsule;

        // Handle auth events
        switch (payload.event) {
          case "signInWithRedirect":
            break;
          case "signInWithRedirect_failure":
            this.clearTokens();
            break;
          case "customOAuthState":
            await this.handleAuthenticationCheck();
            break;
          case "signedIn":
            await this.handleAuthenticationCheck();
            window.location.replace("/");
            break;
          case "signedOut":
            this.clearTokens();
            PermissionTokenCache.clear();
            break;
          case "tokenRefresh":
            await this.handleAuthenticationCheck();
            break;
          case "tokenRefresh_failure":
            this.clearTokens();
            break;
        }
      },
    );
  }

  async signInWithUsernamePassword(
    username: string,
    password: string,
  ): Promise<boolean> {
    try {
      const signInResult = await signIn({ username, password });

      if (signInResult.isSignedIn) {
        await this.handleAuthenticationCheck();
        return true;
      }
      return false;
    } catch (error) {
      return false;
    }
  }

  async signInWithSAML(): Promise<void> {
    try {
      await signInWithRedirect();
    } catch (error) {
      throw error;
    }
  }

  async refreshToken(): Promise<string | null> {
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();

      if (token) {
        StorageHelper.setToken(token);
        return token;
      }

      return null;
    } catch (error) {
      this.clearTokens();
      return null;
    }
  }

  async getToken(): Promise<string | null> {
    try {
      // First try to get from storage for performance
      const storedToken = StorageHelper.getToken();
      if (storedToken) {
        return storedToken;
      }

      // If no stored token, get from current session
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();

      if (token) {
        StorageHelper.setToken(token);
        return token;
      }

      return null;
    } catch (error) {
      return null;
    }
  }

  clearTokens(): void {
    StorageHelper.clearToken();
    StorageHelper.clearRefreshToken();
    PermissionTokenCache.clear();
    StorageHelper.clearUsername();
  }

  async getCredentials() {
    try {
      const session = await fetchAuthSession();
      return session.credentials;
    } catch (error) {
      return null;
    }
  }

  private async handleAuthenticationCheck(): Promise<void> {
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();
      if (token) {
        StorageHelper.setToken(token);
        try {
          const attributes = await fetchUserAttributes();
          if (attributes.email) {
            StorageHelper.setUsername(attributes.email);
          }
        } catch (attrError) {
          // Silent fail
        }
        //window.location.href = '/'; // Redirect to home after successful auth
      } else {
        this.clearTokens();
      }
    } catch (error) {
      this.clearTokens();
    }
  }

  async isAuthenticated(): Promise<boolean> {
    try {
      const user = await getCurrentUser();

      // Double check with session
      const session = await fetchAuthSession();

      const hasValidSession = !!session.tokens?.idToken;

      return !!user && hasValidSession;
    } catch (error) {
      return false;
    }
  }

  async getUserInitial(): Promise<string> {
    try {
      const attributes = await fetchUserAttributes();
      const firstName =
        attributes.given_name || attributes.name?.split(" ")[0] || "";
      return firstName.charAt(0).toUpperCase() || "A";
    } catch (error) {
      return "A";
    }
  }
}

export const authService = new AuthService();
