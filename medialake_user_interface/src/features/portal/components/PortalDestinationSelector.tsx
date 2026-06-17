import React from "react";
import { FormControl, InputLabel, MenuItem, Select, type SelectChangeEvent } from "@mui/material";
import type { PortalDestination } from "../types/portal.types";

interface Props {
  destinations: PortalDestination[];
  selectedDestinationId: string;
  onChange: (destinationId: string) => void;
  disabled?: boolean;
}

const PortalDestinationSelector: React.FC<Props> = ({
  destinations,
  selectedDestinationId,
  onChange,
  disabled,
}) => (
  <FormControl fullWidth disabled={disabled}>
    <InputLabel id="portal-dest-label">Destination</InputLabel>
    <Select
      labelId="portal-dest-label"
      value={selectedDestinationId}
      label="Destination"
      onChange={(e: SelectChangeEvent) => onChange(e.target.value)}
    >
      {destinations.map((d) => (
        <MenuItem key={d.destinationId} value={d.destinationId}>
          {d.friendlyName}
        </MenuItem>
      ))}
    </Select>
  </FormControl>
);

export default PortalDestinationSelector;
