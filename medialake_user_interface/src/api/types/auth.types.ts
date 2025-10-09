// src/api/types/auth.types.ts

import type {
  AuthUser as AmplifyAuthUser,
  AuthTokens,
  FetchUserAttributesOutput,
} from "aws-amplify/auth";

export interface AuthSession {
  accessToken: string;
  idToken: string;
  refreshToken?: string; // Optional since Amplify v6 doesn't expose refresh token
  expiresIn: number;
}

export interface AuthUser extends AmplifyAuthUser {
  username: string;
  email?: string;
  attributes?: FetchUserAttributesOutput; // Optional user attributes
}

export interface AuthError {
  code: string;
  message: string;
  name: string;
}
