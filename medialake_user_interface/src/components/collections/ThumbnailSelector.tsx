import React, { useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Button,
  IconButton,
  Tabs,
  Tab,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  InputAdornment,
  CircularProgress,
  Avatar,
  Tooltip,
  alpha,
} from "@mui/material";
import {
  PhotoCamera as PhotoCameraIcon,
  Image as ImageIcon,
  EmojiEmotions as IconsIcon,
  Delete as DeleteIcon,
  Search as SearchIcon,
  Close as CloseIcon,
  Folder as FolderIcon,
  Collections as CollectionsIcon,
  Star as StarIcon,
  Favorite as FavoriteIcon,
  Work as WorkIcon,
  School as SchoolIcon,
  Home as HomeIcon,
  Business as BusinessIcon,
  AccountBalance as AccountBalanceIcon,
  AttachMoney as AttachMoneyIcon,
  ShoppingCart as ShoppingCartIcon,
  LocalOffer as LocalOfferIcon,
  Category as CategoryIcon,
  Inventory as InventoryIcon,
  Widgets as WidgetsIcon,
  Extension as ExtensionIcon,
  Build as BuildIcon,
  Settings as SettingsIcon,
  Science as ScienceIcon,
  Biotech as BiotechIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Lightbulb as LightbulbIcon,
  Rocket as RocketIcon,
  Explore as ExploreIcon,
  Public as PublicIcon,
  Language as LanguageIcon,
  Cloud as CloudIcon,
  Storage as StorageIcon,
  DataObject as DataObjectIcon,
  Code as CodeIcon,
  Terminal as TerminalIcon,
  Speed as SpeedIcon,
  Timeline as TimelineIcon,
  Analytics as AnalyticsIcon,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  TrendingUp as TrendingUpIcon,
  Insights as InsightsIcon,
  Movie as MovieIcon,
  VideoLibrary as VideoLibraryIcon,
  MusicNote as MusicNoteIcon,
  LibraryMusic as LibraryMusicIcon,
  Photo as PhotoIcon,
  PhotoLibrary as PhotoLibraryIcon,
  CameraAlt as CameraAltIcon,
  Videocam as VideocamIcon,
  Mic as MicIcon,
  Article as ArticleIcon,
  Description as DescriptionIcon,
  Assignment as AssignmentIcon,
  Book as BookIcon,
  MenuBook as MenuBookIcon,
  LibraryBooks as LibraryBooksIcon,
  Newspaper as NewspaperIcon,
  Feed as FeedIcon,
  Forum as ForumIcon,
  Chat as ChatIcon,
  Email as EmailIcon,
  Mail as MailIcon,
  Notifications as NotificationsIcon,
  Event as EventIcon,
  CalendarMonth as CalendarMonthIcon,
  Schedule as ScheduleIcon,
  Alarm as AlarmIcon,
  People as PeopleIcon,
  Group as GroupIcon,
  Person as PersonIcon,
  Face as FaceIcon,
  EmojiPeople as EmojiPeopleIcon,
  Diversity1 as Diversity1Icon,
  Handshake as HandshakeIcon,
  SupportAgent as SupportAgentIcon,
  Nature as NatureIcon,
  Park as ParkIcon,
  Forest as ForestIcon,
  Grass as GrassIcon,
  LocalFlorist as LocalFloristIcon,
  Pets as PetsIcon,
  Spa as SpaIcon,
  Restaurant as RestaurantIcon,
  LocalCafe as LocalCafeIcon,
  LocalBar as LocalBarIcon,
  Cake as CakeIcon,
  Fastfood as FastfoodIcon,
  Flight as FlightIcon,
  DirectionsCar as DirectionsCarIcon,
  Train as TrainIcon,
  DirectionsBike as DirectionsBikeIcon,
  DirectionsWalk as DirectionsWalkIcon,
  Luggage as LuggageIcon,
  BeachAccess as BeachAccessIcon,
  Hiking as HikingIcon,
  FitnessCenter as FitnessCenterIcon,
  SportsBasketball as SportsBasketballIcon,
  SportsEsports as SportsEsportsIcon,
  Games as GamesIcon,
  Casino as CasinoIcon,
  Palette as PaletteIcon,
  Brush as BrushIcon,
  ColorLens as ColorLensIcon,
  Architecture as ArchitectureIcon,
  Draw as DrawIcon,
  DesignServices as DesignServicesIcon,
  AutoFixHigh as AutoFixHighIcon,
  Healing as HealingIcon,
  LocalHospital as LocalHospitalIcon,
  MedicalServices as MedicalServicesIcon,
  Favorite as HeartIcon,
  Shield as ShieldIcon,
  Security as SecurityIcon,
  Lock as LockIcon,
  Key as KeyIcon,
  Verified as VerifiedIcon,
  CheckCircle as CheckCircleIcon,
  TaskAlt as TaskAltIcon,
  Flag as FlagIcon,
  Bookmark as BookmarkIcon,
  Label as LabelIcon,
  Tag as TagIcon,
  LocalActivity as LocalActivityIcon,
  CardGiftcard as CardGiftcardIcon,
  Celebration as CelebrationIcon,
  EmojiEvents as EmojiEventsIcon,
  MilitaryTech as MilitaryTechIcon,
  WorkspacePremium as WorkspacePremiumIcon,
} from "@mui/icons-material";
import type { SvgIconComponent } from "@mui/icons-material";
import type { ThumbnailType } from "../../api/hooks/useCollections";

// Icon mapping - organized by category
const ICON_CATEGORIES = {
  general: {
    label: "General",
    icons: {
      Folder: FolderIcon,
      Collections: CollectionsIcon,
      Star: StarIcon,
      Favorite: FavoriteIcon,
      Bookmark: BookmarkIcon,
      Label: LabelIcon,
      Tag: TagIcon,
      Flag: FlagIcon,
      CheckCircle: CheckCircleIcon,
      TaskAlt: TaskAltIcon,
    },
  },
  business: {
    label: "Business",
    icons: {
      Work: WorkIcon,
      Business: BusinessIcon,
      AccountBalance: AccountBalanceIcon,
      AttachMoney: AttachMoneyIcon,
      ShoppingCart: ShoppingCartIcon,
      LocalOffer: LocalOfferIcon,
      Handshake: HandshakeIcon,
      SupportAgent: SupportAgentIcon,
      Assignment: AssignmentIcon,
      TrendingUp: TrendingUpIcon,
    },
  },
  media: {
    label: "Media",
    icons: {
      Movie: MovieIcon,
      VideoLibrary: VideoLibraryIcon,
      MusicNote: MusicNoteIcon,
      LibraryMusic: LibraryMusicIcon,
      Photo: PhotoIcon,
      PhotoLibrary: PhotoLibraryIcon,
      CameraAlt: CameraAltIcon,
      Videocam: VideocamIcon,
      Mic: MicIcon,
      Image: ImageIcon,
    },
  },
  documents: {
    label: "Documents",
    icons: {
      Article: ArticleIcon,
      Description: DescriptionIcon,
      Book: BookIcon,
      MenuBook: MenuBookIcon,
      LibraryBooks: LibraryBooksIcon,
      Newspaper: NewspaperIcon,
      Feed: FeedIcon,
      Email: EmailIcon,
      Mail: MailIcon,
      Notifications: NotificationsIcon,
    },
  },
  technology: {
    label: "Technology",
    icons: {
      Code: CodeIcon,
      Terminal: TerminalIcon,
      DataObject: DataObjectIcon,
      Storage: StorageIcon,
      Cloud: CloudIcon,
      Settings: SettingsIcon,
      Build: BuildIcon,
      Extension: ExtensionIcon,
      Widgets: WidgetsIcon,
      Speed: SpeedIcon,
    },
  },
  analytics: {
    label: "Analytics",
    icons: {
      Analytics: AnalyticsIcon,
      BarChart: BarChartIcon,
      PieChart: PieChartIcon,
      Timeline: TimelineIcon,
      Insights: InsightsIcon,
      Science: ScienceIcon,
      Biotech: BiotechIcon,
      Psychology: PsychologyIcon,
      Lightbulb: LightbulbIcon,
      AutoAwesome: AutoAwesomeIcon,
    },
  },
  people: {
    label: "People",
    icons: {
      People: PeopleIcon,
      Group: GroupIcon,
      Person: PersonIcon,
      Face: FaceIcon,
      EmojiPeople: EmojiPeopleIcon,
      Diversity1: Diversity1Icon,
      School: SchoolIcon,
      Home: HomeIcon,
      Forum: ForumIcon,
      Chat: ChatIcon,
    },
  },
  creative: {
    label: "Creative",
    icons: {
      Palette: PaletteIcon,
      Brush: BrushIcon,
      ColorLens: ColorLensIcon,
      Architecture: ArchitectureIcon,
      Draw: DrawIcon,
      DesignServices: DesignServicesIcon,
      AutoFixHigh: AutoFixHighIcon,
      Category: CategoryIcon,
      Inventory: InventoryIcon,
      Rocket: RocketIcon,
    },
  },
  travel: {
    label: "Travel & Lifestyle",
    icons: {
      Flight: FlightIcon,
      DirectionsCar: DirectionsCarIcon,
      Train: TrainIcon,
      Explore: ExploreIcon,
      Public: PublicIcon,
      Language: LanguageIcon,
      Luggage: LuggageIcon,
      BeachAccess: BeachAccessIcon,
      Hiking: HikingIcon,
      Nature: NatureIcon,
    },
  },
  events: {
    label: "Events & Awards",
    icons: {
      Event: EventIcon,
      CalendarMonth: CalendarMonthIcon,
      Schedule: ScheduleIcon,
      Celebration: CelebrationIcon,
      EmojiEvents: EmojiEventsIcon,
      MilitaryTech: MilitaryTechIcon,
      WorkspacePremium: WorkspacePremiumIcon,
      CardGiftcard: CardGiftcardIcon,
      LocalActivity: LocalActivityIcon,
      Verified: VerifiedIcon,
    },
  },
};

// Flatten icons for search
export const ALL_ICONS: Record<string, SvgIconComponent> = Object.values(ICON_CATEGORIES).reduce(
  (acc, category) => ({ ...acc, ...category.icons }),
  {}
);

interface ThumbnailSelectorProps {
  currentThumbnailType?: ThumbnailType;
  currentThumbnailValue?: string;
  currentThumbnailUrl?: string;
  onSelectIcon: (iconName: string) => void;
  onUploadImage: (base64Data: string) => void;
  onRemoveThumbnail: () => void;
  isLoading?: boolean;
  disabled?: boolean;
}

type TabValue = "current" | "icons" | "upload";

export const ThumbnailSelector: React.FC<ThumbnailSelectorProps> = ({
  currentThumbnailType,
  currentThumbnailValue,
  currentThumbnailUrl,
  onSelectIcon,
  onUploadImage,
  onRemoveThumbnail,
  isLoading = false,
  disabled = false,
}) => {
  const { t } = useTranslation();

  const [activeTab, setActiveTab] = useState<TabValue>("current");
  const [iconSearch, setIconSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("general");
  const [iconPickerOpen, setIconPickerOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasThumbnail = currentThumbnailType && (currentThumbnailUrl || currentThumbnailValue);

  // Get current icon component
  const CurrentIconComponent =
    currentThumbnailType === "icon" && currentThumbnailValue
      ? ALL_ICONS[currentThumbnailValue]
      : null;

  // Filter icons by search
  const filteredIcons = iconSearch
    ? Object.entries(ALL_ICONS).filter(([name]) =>
        name.toLowerCase().includes(iconSearch.toLowerCase())
      )
    : Object.entries(
        ICON_CATEGORIES[selectedCategory as keyof typeof ICON_CATEGORIES]?.icons || {}
      );

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      // Validate file type
      if (!file.type.startsWith("image/")) {
        alert(t("collections.thumbnail.invalidFileType", "Please select an image file"));
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        alert(t("collections.thumbnail.fileTooLarge", "Image must be less than 5MB"));
        return;
      }

      // Read file as base64
      const reader = new FileReader();
      reader.onload = (e) => {
        const base64 = e.target?.result as string;
        // Remove the data URL prefix to get just the base64 data
        const base64Data = base64.split(",")[1];
        onUploadImage(base64Data);
      };
      reader.readAsDataURL(file);

      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [onUploadImage, t]
  );

  const handleIconSelect = useCallback(
    (iconName: string) => {
      onSelectIcon(iconName);
      setIconPickerOpen(false);
    },
    [onSelectIcon]
  );

  const PREVIEW_WIDTH = 200;
  const PREVIEW_HEIGHT = 120;

  const renderCurrentThumbnail = () => {
    if (isLoading) {
      return (
        <Box
          sx={{
            width: PREVIEW_WIDTH,
            height: PREVIEW_HEIGHT,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "action.hover",
            borderRadius: 2,
          }}
        >
          <CircularProgress size={32} />
        </Box>
      );
    }

    if (currentThumbnailType === "icon" && CurrentIconComponent) {
      return (
        <Avatar
          variant="rounded"
          sx={{
            width: PREVIEW_WIDTH,
            height: PREVIEW_HEIGHT,
            bgcolor: "primary.main",
            borderRadius: 2,
          }}
        >
          <CurrentIconComponent sx={{ fontSize: 56 }} />
        </Avatar>
      );
    }

    if (currentThumbnailUrl) {
      return (
        <Box
          component="img"
          src={currentThumbnailUrl}
          alt="Collection thumbnail"
          sx={{
            width: PREVIEW_WIDTH,
            height: PREVIEW_HEIGHT,
            objectFit: "cover",
            borderRadius: 2,
            border: "1px solid",
            borderColor: "divider",
          }}
        />
      );
    }

    // Default placeholder
    return (
      <Avatar
        variant="rounded"
        sx={{
          width: PREVIEW_WIDTH,
          height: PREVIEW_HEIGHT,
          bgcolor: "action.hover",
          borderRadius: 2,
        }}
      >
        <FolderIcon sx={{ fontSize: 56, color: "text.secondary" }} />
      </Avatar>
    );
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
        {t("collections.thumbnail.title", "Collection Thumbnail")}
      </Typography>

      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
        {/* Current thumbnail preview */}
        <Box sx={{ position: "relative" }}>
          {renderCurrentThumbnail()}
          {hasThumbnail && !disabled && (
            <IconButton
              size="small"
              onClick={onRemoveThumbnail}
              disabled={isLoading}
              sx={{
                position: "absolute",
                top: -8,
                right: -8,
                bgcolor: "error.main",
                color: "white",
                "&:hover": { bgcolor: "error.dark" },
                width: 24,
                height: 24,
              }}
            >
              <CloseIcon sx={{ fontSize: 14 }} />
            </IconButton>
          )}
        </Box>

        {/* Action buttons */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<IconsIcon />}
            onClick={() => setIconPickerOpen(true)}
            disabled={disabled || isLoading}
          >
            {t("collections.thumbnail.chooseIcon", "Choose Icon")}
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PhotoCameraIcon />}
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isLoading}
          >
            {t("collections.thumbnail.uploadImage", "Upload Image")}
          </Button>
          {hasThumbnail && (
            <Button
              variant="outlined"
              size="small"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={onRemoveThumbnail}
              disabled={disabled || isLoading}
            >
              {t("collections.thumbnail.remove", "Remove")}
            </Button>
          )}
        </Box>
      </Box>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />

      {/* Icon picker dialog */}
      <Dialog
        open={iconPickerOpen}
        onClose={() => setIconPickerOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{t("collections.thumbnail.selectIcon", "Select an Icon")}</DialogTitle>
        <DialogContent>
          {/* Search */}
          <TextField
            fullWidth
            size="small"
            placeholder={t("collections.thumbnail.searchIcons", "Search icons...")}
            value={iconSearch}
            onChange={(e) => setIconSearch(e.target.value)}
            sx={{ mb: 2 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
              endAdornment: iconSearch && (
                <InputAdornment position="end">
                  <IconButton size="small" onClick={() => setIconSearch("")}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          {/* Category tabs (only shown when not searching) */}
          {!iconSearch && (
            <Tabs
              value={selectedCategory}
              onChange={(_, value) => setSelectedCategory(value)}
              variant="scrollable"
              scrollButtons="auto"
              sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
            >
              {Object.entries(ICON_CATEGORIES).map(([key, { label }]) => (
                <Tab key={key} value={key} label={label} />
              ))}
            </Tabs>
          )}

          {/* Icon grid */}
          <Box sx={{ maxHeight: 400, overflow: "auto" }}>
            <Grid container spacing={1}>
              {filteredIcons.map(([name, IconComponent]) => (
                <Grid item key={name}>
                  <Tooltip title={name}>
                    <IconButton
                      onClick={() => handleIconSelect(name)}
                      sx={{
                        width: 48,
                        height: 48,
                        borderRadius: 1,
                        border: "1px solid",
                        borderColor:
                          currentThumbnailType === "icon" && currentThumbnailValue === name
                            ? "primary.main"
                            : "transparent",
                        bgcolor:
                          currentThumbnailType === "icon" && currentThumbnailValue === name
                            ? (theme) => alpha(theme.palette.primary.main, 0.1)
                            : "transparent",
                        "&:hover": {
                          bgcolor: "action.hover",
                          borderColor: "primary.light",
                        },
                      }}
                    >
                      <IconComponent />
                    </IconButton>
                  </Tooltip>
                </Grid>
              ))}
            </Grid>
            {filteredIcons.length === 0 && (
              <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
                {t("collections.thumbnail.noIconsFound", "No icons found")}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIconPickerOpen(false)}>{t("common.cancel", "Cancel")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ThumbnailSelector;
