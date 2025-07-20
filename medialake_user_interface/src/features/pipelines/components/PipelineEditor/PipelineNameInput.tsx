import React from "react";
import { TextField } from "@mui/material";

interface PipelineNameInputProps {
  value: string;
  onChange: (value: string) => void;
}

const PipelineNameInput: React.FC<PipelineNameInputProps> = ({
  value,
  onChange,
}) => {
  return (
    <TextField
      fullWidth
      variant="outlined"
      size="small"
      placeholder="Pipeline Name"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      sx={{
        "& .MuiOutlinedInput-root": {
          borderRadius: "4px",
          backgroundColor: "transparent",
        },
        width: "100%", // Use 100% width to fill the container
        minWidth: "150px", // Minimum width to ensure readability
        maxWidth: "300px", // Maximum width to prevent it from getting too large
      }}
    />
  );
};

export default PipelineNameInput;
