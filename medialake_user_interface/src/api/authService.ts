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
        console.log("Auth event:", payload.event, payload);

        // Log all auth events for debugging
        console.log("Auth event details:", {
          event: payload.event,
          message: payload.message,
        });

        // Handle auth events
        switch (payload.event) {
          case "signInWithRedirect":
            console.log("Starting SAML redirect flow...");
            break;
          case "signInWithRedirect_failure":
            console.error("SAML redirect failed");
            this.clearTokens();
            break;
          case "customOAuthState":
            console.log("Custom OAuth state received");
            await this.handleAuthenticationCheck();
            break;
          case "signedIn":
            console.log("User signed in");
            await this.handleAuthenticationCheck();
            window.location.replace("/");
            break;
          case "signedOut":
            console.log("User signed out");
            this.clearTokens();
            PermissionTokenCache.clear();
            break;
          case "tokenRefresh":
            console.log("Token refresh occurred");
            await this.handleAuthenticationCheck();
            break;
          case "tokenRefresh_failure":
            console.error("Token refresh failed");
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
      console.log("Username/password sign in result:", signInResult);

      if (signInResult.isSignedIn) {
        await this.handleAuthenticationCheck();
        return true;
      }
      return false;
    } catch (error) {
      console.error("Username/password sign in failed:", error);
      return false;
    }
  }

  async signInWithSAML(): Promise<void> {
    try {
      await signInWithRedirect();
    } catch (error) {
      console.error("SAML sign in failed:", error);
      throw error;
    }
  }

  async refreshToken(): Promise<string | null> {
    console.log("Starting token refresh process...");
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();

      if (token) {
        console.log("Session refresh successful");
        console.log("=== Refreshed Token Claims ===");
        const tokenParts = token.split(".");
        if (tokenParts.length === 3) {
          const payload = JSON.parse(atob(tokenParts[1]));
          console.log(
            "Refreshed token claims:",
            JSON.stringify(payload, null, 2),
          );
          console.log(
            "cognito:groups after refresh:",
            payload["cognito:groups"],
          );
          console.log(
            "custom:permissions after refresh:",
            payload["custom:permissions"],
          );
        }
        console.log("=============================");
        StorageHelper.setToken(token);
        return token;
      }

      console.error("No token in refreshed session");
      return null;
    } catch (error) {
      console.error("Failed to refresh token:", error);
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
      console.error("Error getting token:", error);
      return null;
    }
  }

  clearTokens(): void {
    console.log("Clearing all tokens...");
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
      console.error("Error getting credentials:", error);
      return null;
    }
  }

  private async handleAuthenticationCheck(): Promise<void> {
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();
      if (token) {
        console.log("=== handleAuthenticationCheck Token ===");
        const tokenParts = token.split(".");
        if (tokenParts.length === 3) {
          const payload = JSON.parse(atob(tokenParts[1]));
          console.log(
            "Token claims in auth check:",
            JSON.stringify(payload, null, 2),
          );
          console.log(
            "cognito:groups in auth check:",
            payload["cognito:groups"],
          );
        }
        console.log("======================================");
        StorageHelper.setToken(token);
        try {
          const attributes = await fetchUserAttributes();
          console.log("User attributes:", attributes);
          if (attributes.email) {
            StorageHelper.setUsername(attributes.email);
          }
        } catch (attrError) {
          console.error("Error fetching user attributes:", attrError);
        }
        //window.location.href = '/'; // Redirect to home after successful auth
      } else {
        console.error("No token in session");
        this.clearTokens();
      }
    } catch (error) {
      console.error("Error during authentication check:", error);
      this.clearTokens();
    }
  }

  async isAuthenticated(): Promise<boolean> {
    try {
      const user = await getCurrentUser();
      console.log("Current user:", user);

      // Double check with session
      const session = await fetchAuthSession();
      console.log("Current session:", session);

      const hasValidSession = !!session.tokens?.idToken;
      console.log("Has valid session:", hasValidSession);

      return !!user && hasValidSession;
    } catch (error) {
      console.error("Error checking authentication status:", error);
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
      console.error("Error getting user attributes:", error);
      return "A";
    }
  }
}

export const authService = new AuthService();
