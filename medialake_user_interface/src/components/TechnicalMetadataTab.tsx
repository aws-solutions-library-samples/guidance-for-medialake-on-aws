import React, { useState, useMemo } from "react";
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  FormControl,
  Select,
  MenuItem,
  Chip,
  useTheme,
  alpha,
} from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import SearchIcon from "@mui/icons-material/Search";
import MetadataContent from "./MetadataContent";

// Category mapping for display names
const categoryMapping = {
  exif: "EXIF",
  ifd1: "Thumbnail (IFD1)",
  ifd0: "Image (IFD0)",
  gps: "GPS",
  iptc: "IPTC",
  xmp: "XMP",
  icc: "ICC",
  jfif: "JFIF (JPEG only)",
  ihdr: "IHDR (PNG only)",
  makerNote: "Maker Note",
  userComment: "User Comment",
  xmpRights: "Rights",
  Iptc4xmpCore: "IPTC Core",
  Iptc4xmpExt: "IPTC Extension",
  photoshop: "Photoshop",
  plus: "PLUS",
  dc: "Dublin Core",
  xmpMM: "XMP Media Management",
  aux: "Auxiliary",
  crs: "Camera Raw Settings",
  exifEX: "EXIF Extended",
  xmpDM: "XMP Dynamic Media",
  interop: "Interoperability",
  // Audio-specific categories
  id3v2: "ID3v2",
  mp3Info: "MP3 Info",
  flac: "FLAC",
  wav: "WAV",
  oggVorbis: "Ogg Vorbis",
  audioMetadata: "Audio Metadata",
  technical: "Technical",
  musicBrainz: "MusicBrainz",
  encoding: "Encoding",
  rights: "Rights",
  // Add mapping for ObjectMetadata to display as "Object Metadata"
  ObjectMetadata: "Object Metadata",
};

interface TechnicalMetadataTabProps {
  metadataAccordions: any[];
  availableCategories: string[];
  mediaType?: "image" | "audio" | "video";
}

const TechnicalMetadataTab: React.FC<TechnicalMetadataTabProps> = ({
  metadataAccordions,
  availableCategories,
  mediaType = "image",
}) => {
  const theme = useTheme();

  /* ---------------------------------------------------------------------- */
  /*  Local UI state                                                     */
  /* ---------------------------------------------------------------------- */

  const [categoryFilter, setCategoryFilter] = useState<"all" | string>("all");
  const [textFilter, setTextFilter] = useState("");

  /* ---------------------------------------------------------------------- */
  /*  Filter the accordion list whenever UI filters change              */
  /* ---------------------------------------------------------------------- */

  const filteredAccordions = useMemo(() => {
    let result = metadataAccordions;

    // category filter
    if (categoryFilter !== "all") {
      result = result
        .map((parent) => {
          const subCategories = parent.subCategories.filter(
            (sub: any) =>
              sub.category.toLowerCase() === categoryFilter.toLowerCase(),
          );
          return subCategories.length
            ? { ...parent, subCategories, count: subCategories.length }
            : null;
        })
        .filter(Boolean);
    }

    // text filter (inside key/value pairs)
    if (textFilter.trim()) {
      const term = textFilter.toLowerCase();
      result = result
        .map((parent) => {
          const subCategories = parent.subCategories.filter((sub: any) =>
            JSON.stringify(sub.data).toLowerCase().includes(term),
          );
          return subCategories.length
            ? { ...parent, subCategories, count: subCategories.length }
            : null;
        })
        .filter(Boolean);
    }

    return result;
  }, [metadataAccordions, categoryFilter, textFilter]);

  /* ---------------------------------------------------------------------- */
  /* Default-expand everything that survived the filter                */
  /* ---------------------------------------------------------------------- */

  const expandedItems = useMemo(() => {
    const all: string[] = [];
    filteredAccordions.forEach((parent, pIdx) => {
      all.push(`parent-${pIdx}`);
      parent.subCategories.forEach((_: any, sIdx: number) =>
        all.push(`${pIdx}-${sIdx}`),
      );
    });
    return all;
  }, [filteredAccordions]);

  /* ---------------------------------------------------------------------- */
  /* Helper to render the sub-category body                             */
  /* ---------------------------------------------------------------------- */

  const getContentComponent = (subCategory: any) => (
    <MetadataContent
      data={subCategory.data}
      showAll
      category={subCategory.category}
      mediaType={mediaType}
    />
  );

  /* ---------------------------------------------------------------------- */
  /* UI                                                                 */
  /* ---------------------------------------------------------------------- */

  return (
    <Box sx={{ borderRadius: 1, width: "100%" }}>
      {/* --------------------------------------------------  Filter bar  --- */}
      <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 2 }}>
        <TextField
          placeholder="Filter metadata…"
          size="small"
          value={textFilter}
          onChange={(e) => setTextFilter(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ flex: 1, px: 2 }}
        />

        <FormControl size="small" sx={{ minWidth: 140, px: 2 }}>
          <Select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as string)}
            displayEmpty
          >
            <MenuItem value="all">All Categories</MenuItem>
            {availableCategories.map((key) => (
              <MenuItem key={key} value={key}>
                {categoryMapping[key] ||
                  key.charAt(0).toUpperCase() + key.slice(1)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* ----------------------------------------------  Metadata tree  --- */}
      <SimpleTreeView
        defaultExpandedItems={expandedItems}
        sx={{
          "& .MuiTreeItem-content": {
            padding: "4px 8px",
            borderRadius: "4px",
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.main, 0.05),
            },
          },
          "& .MuiTreeItem-group": {
            marginLeft: "24px",
            borderLeft: `1px dashed ${alpha(theme.palette.text.primary, 0.2)}`,
            paddingLeft: "8px",
          },
        }}
        slots={{ collapseIcon: ExpandMoreIcon, expandIcon: ChevronRightIcon }}
      >
        {filteredAccordions.map((parent, pIdx) => (
          <TreeItem
            key={pIdx}
            itemId={`parent-${pIdx}`}
            label={
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                  {parent.category === "EmbeddedMetadata"
                    ? "Embedded Metadata"
                    : categoryMapping[
                        parent.category as keyof typeof categoryMapping
                      ] || parent.category}
                </Typography>
                <Chip
                  size="small"
                  label={parent.count}
                  sx={{
                    ml: 1,
                    height: 20,
                    fontSize: "0.70rem",
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    color: theme.palette.primary.main,
                  }}
                />
              </Box>
            }
          >
            {parent.subCategories.map((sub: any, sIdx: number) => (
              <TreeItem
                key={sIdx}
                itemId={`${pIdx}-${sIdx}`}
                label={
                  <Box sx={{ display: "flex", alignItems: "center" }}>
                    <Typography variant="body2">
                      {categoryMapping[
                        sub.category as keyof typeof categoryMapping
                      ] || sub.category}
                    </Typography>
                    <Chip
                      size="small"
                      label={sub.count}
                      sx={{
                        ml: 1,
                        height: 18,
                        fontSize: "0.65rem",
                        backgroundColor: alpha(
                          theme.palette.secondary.main,
                          0.1,
                        ),
                        color: theme.palette.secondary.main,
                      }}
                    />
                  </Box>
                }
              >
                <Box
                  sx={{
                    p: 2,
                    mt: 1,
                    backgroundColor: alpha(theme.palette.background.paper, 0.5),
                    borderRadius: 1,
                  }}
                >
                  {getContentComponent(sub)}
                </Box>
              </TreeItem>
            ))}
          </TreeItem>
        ))}
      </SimpleTreeView>
    </Box>
  );
};

export default TechnicalMetadataTab;
export { categoryMapping };
