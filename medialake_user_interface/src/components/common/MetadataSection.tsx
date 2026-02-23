import React from "react";
import { Box, Tab, Tabs } from "@mui/material";
import { styled } from "@mui/material/styles";

const StyledTabs = styled(Tabs)(({ theme }) => ({
  "& .MuiTabs-indicator": {
    backgroundColor: theme.palette.primary.main,
    height: "2px",
  },
}));

const StyledTab = styled(Tab)(({ theme }) => ({
  textTransform: "none",
  fontSize: "16px",
  fontWeight: 400,
  color: theme.palette.text.secondary,
  padding: "12px 0",
  marginRight: "32px",
  minWidth: "unset",
  "&.Mui-selected": {
    color: theme.palette.primary.main,
  },
}));

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <Box
      role="tabpanel"
      hidden={value !== index}
      id={`metadata-tabpanel-${index}`}
      aria-labelledby={`metadata-tab-${index}`}
      sx={{
        py: 3,
      }}
      {...other}
    >
      {value === index && children}
    </Box>
  );
};

interface MetadataTab {
  label: string;
  content: React.ReactNode;
}

interface MetadataSectionProps {
  tabs: MetadataTab[];
  defaultTab?: number;
  onTabChange?: (newValue: number) => void;
}

const MetadataSection: React.FC<MetadataSectionProps> = ({ tabs, defaultTab = 0, onTabChange }) => {
  const [value, setValue] = React.useState(defaultTab);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
    if (onTabChange) {
      onTabChange(newValue);
    }
  };

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <StyledTabs value={value} onChange={handleChange} aria-label="metadata tabs">
          {tabs.map((tab, index) => (
            <StyledTab
              key={index}
              label={tab.label}
              id={`metadata-tab-${index}`}
              aria-controls={`metadata-tabpanel-${index}`}
            />
          ))}
        </StyledTabs>
      </Box>

      {tabs.map((tab, index) => (
        <TabPanel key={index} value={value} index={index}>
          {tab.content}
        </TabPanel>
      ))}
    </Box>
  );
};

export default MetadataSection;
