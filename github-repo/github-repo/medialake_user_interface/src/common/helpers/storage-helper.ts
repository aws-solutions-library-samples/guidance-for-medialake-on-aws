import { NavigationPanelState } from "../types";

const PREFIX = "medialake";
const THEME_STORAGE_NAME = `${PREFIX}-theme`;
const NAVIGATION_PANEL_STATE_STORAGE_NAME = `${PREFIX}-navigation-panel-state`;
const TOKEN_KEY = `${PREFIX}-auth-token`;
const REFRESH_TOKEN_KEY = `${PREFIX}-refresh-token`;
const USERNAME_KEY = `${PREFIX}-username`;
const AWS_CONFIG_KEY = `${PREFIX}-aws-config`;

export abstract class StorageHelper {
  static getTheme(): "light" | "dark" {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme === "dark" ? "dark" : "light";
  }

  static setTheme(theme: "light" | "dark"): void {
    localStorage.setItem("theme", theme);
  }

  static getNavigationPanelState(): NavigationPanelState {
    const value =
      localStorage.getItem(NAVIGATION_PANEL_STATE_STORAGE_NAME) ??
      JSON.stringify({
        collapsed: true,
      });

    let state: NavigationPanelState | null = null;
    try {
      state = JSON.parse(value);
    } catch {
      state = {};
    }

    return state ?? {};
  }

  static setNavigationPanelState(state: Partial<NavigationPanelState>) {
    const currentState = this.getNavigationPanelState();
    const newState = { ...currentState, ...state };
    const stateStr = JSON.stringify(newState);
    localStorage.setItem(NAVIGATION_PANEL_STATE_STORAGE_NAME, stateStr);

    return newState;
  }

  static setAwsConfig(config: any) {
    localStorage.setItem(AWS_CONFIG_KEY, JSON.stringify(config));
  }

  static getAwsConfig(): any | null {
    const configString = localStorage.getItem(AWS_CONFIG_KEY);
    return configString ? JSON.parse(configString) : null;
  }

  static clearAwsConfig() {
    localStorage.removeItem(AWS_CONFIG_KEY);
  }

  static setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  }

  static getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  static clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  static setRefreshToken(token: string) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  }

  static getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  static clearRefreshToken() {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  static setUsername(username: string) {
    localStorage.setItem(USERNAME_KEY, username);
  }

  static getUsername(): string | null {
    return localStorage.getItem(USERNAME_KEY);
  }

  static clearUsername() {
    localStorage.removeItem(USERNAME_KEY);
  }
}
