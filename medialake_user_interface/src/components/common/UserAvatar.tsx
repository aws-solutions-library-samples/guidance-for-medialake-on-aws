import React, { useState, useEffect } from "react";
import { Avatar, useTheme } from "@mui/material";
import { fetchUserAttributes } from "aws-amplify/auth";

interface UserAvatarProps {
  size?: number;
  fontSize?: string;
  sx?: any;
}

export const UserAvatar: React.FC<UserAvatarProps> = ({
  size = 24,
  fontSize = "0.875rem",
  sx = {},
}) => {
  const theme = useTheme();
  const [userInitial, setUserInitial] = useState<string>("U");

  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        const attributes = await fetchUserAttributes();
        const email = attributes.email;

        if (email && email.trim()) {
          setUserInitial(email.trim()[0].toUpperCase());
        }
      } catch (error) {
        console.error("Error fetching user attributes:", error);
        setUserInitial("U");
      }
    };

    fetchUserInfo();
  }, []);

  return (
    <Avatar
      sx={{
        width: size,
        height: size,
        bgcolor: theme.palette.primary.main,
        fontSize: fontSize,
        flexShrink: 0,
        ...sx,
      }}
    >
      {userInitial}
    </Avatar>
  );
};
