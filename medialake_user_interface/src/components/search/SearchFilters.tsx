import React from "react";
import {
  List,
  ListItemText,
  ListItemIcon,
  Radio,
  Checkbox,
  ListItemButton,
  Divider,
  Collapse,
} from "@mui/material";
import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";

const filterLabels = {
  recent: "Recent",
  lastWeek: "Last Week",
  lastMonth: "Last Month",
  lastYear: "Last Year",
  videos: "Videos",
  images: "Images",
  audio: "Audio",
};

interface FiltersState {
  mediaTypes: {
    videos: boolean;
    images: boolean;
    audio: boolean;
  };
  time: {
    recent: boolean;
    lastWeek: boolean;
    lastMonth: boolean;
    lastYear: boolean;
  };
  // status: {
  //     favorites: boolean;
  //     archived: boolean;
  //     shared: boolean;
  // };
}

interface ExpandedSections {
  mediaTypes: boolean;
  time: boolean;
  status: boolean;
}

interface SearchFiltersProps {
  filters: FiltersState;
  expandedSections: ExpandedSections;
  onFilterChange: (section: string, filter: string) => void;
  onSectionToggle: (section: string) => void;
}

const SearchFilters: React.FC<SearchFiltersProps> = ({
  filters,
  expandedSections,
  onFilterChange,
  onSectionToggle,
}) => {
  const renderFilterSection = (
    title: string,
    section: string,
    items: Record<string, boolean>,
  ) => (
    <>
      <ListItemButton
        onClick={() => onSectionToggle(section)}
        sx={{
          py: 1,
          minHeight: 40,
          px: 2,
          "&:hover": {
            bgcolor: "action.hover",
          },
        }}
      >
        <ListItemText
          primary={title}
          primaryTypographyProps={{
            fontWeight: 600,
            fontSize: "0.875rem",
          }}
        />
        {expandedSections[section as keyof typeof expandedSections] ? (
          <ExpandLess />
        ) : (
          <ExpandMore />
        )}
      </ListItemButton>
      <Collapse
        in={expandedSections[section as keyof typeof expandedSections]}
        timeout="auto"
      >
        <List component="div" disablePadding>
          {Object.entries(items).map(([key, value]) => (
            <ListItemButton
              key={key}
              onClick={() => onFilterChange(section, key)}
              sx={{
                pl: 3,
                py: 0.75,
                "&:hover": {
                  bgcolor: "action.hover",
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                {section === "time" ? (
                  <Radio
                    edge="start"
                    checked={value}
                    tabIndex={-1}
                    disableRipple
                    size="small"
                    sx={{
                      color: "primary.main",
                      "&.Mui-checked": {
                        color: "primary.main",
                      },
                    }}
                  />
                ) : (
                  <Checkbox
                    edge="start"
                    checked={value}
                    tabIndex={-1}
                    disableRipple
                    size="small"
                    sx={{
                      color: "primary.main",
                      "&.Mui-checked": {
                        color: "primary.main",
                      },
                    }}
                  />
                )}
              </ListItemIcon>
              <ListItemText
                primary={filterLabels[key as keyof typeof filterLabels]}
                primaryTypographyProps={{
                  variant: "body2",
                  sx: {
                    fontWeight: value ? 500 : 400,
                    fontSize: "0.8125rem",
                  },
                }}
              />
            </ListItemButton>
          ))}
        </List>
      </Collapse>
      <Divider />
    </>
  );

  return (
    <List component="nav" sx={{ width: "100%" }}>
      {renderFilterSection("Media Types", "mediaTypes", filters.mediaTypes)}
      {renderFilterSection("Time Period", "time", filters.time)}
    </List>
  );
};

export default SearchFilters;
