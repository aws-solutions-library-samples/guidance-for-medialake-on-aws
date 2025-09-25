import { jwtDecode } from "jwt-decode";

interface JwtPayload {
  exp: number;
}

export const isTokenExpiringSoon = (
  token: string,
  bufferTimeInSeconds: number = 300,
): boolean => {
  try {
    const { exp } = jwtDecode<JwtPayload>(token);
    const currentTime = Math.floor(Date.now() / 1000);
    return exp - currentTime < bufferTimeInSeconds;
  } catch (error) {
    console.error("Error decoding token:", error);
    return true; // Assume token is expiring if there's an error
  }
};
