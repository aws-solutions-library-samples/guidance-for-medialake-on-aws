// components/TopBar/hooks/useTopBar.ts
import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { signOut } from "aws-amplify/auth";
import { useSearch } from "@/api/hooks/useSearch";
import type { SearchFilters } from "@/types/search";
import { INITIAL_FILTER_OPTIONS } from "../constants";
import type { FilterOptions } from "../types";
import { useAuth } from "../../../common/hooks/auth-context";
import { StorageHelper } from "../../../common/helpers/storage-helper";

export const useTopBar = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterAnchorEl, setFilterAnchorEl] = useState<HTMLElement | null>(
    null,
  );
  const [filterOptions, setFilterOptions] = useState<FilterOptions>(
    INITIAL_FILTER_OPTIONS,
  );
  const [chatVisible, setChatVisible] = useState(false);

  const navigate = useNavigate();
  const { refetch } = useSearch(searchQuery);
  const { setIsAuthenticated } = useAuth();

  const handleSearchChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(event.target.value);
    },
    [],
  );

  const handleFilterClick = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      setFilterAnchorEl(event.currentTarget);
    },
    [],
  );

  const handleFilterClose = useCallback(() => {
    setFilterAnchorEl(null);
  }, []);

  const handleDateChange = useCallback(
    (type: "before" | "after") => (date: Date | null) => {
      setFilterOptions((prevState) => ({
        ...prevState,
        creationDate: {
          ...prevState.creationDate,
          [type]: date,
        },
      }));
    },
    [],
  );

  const handleSearchSubmit = useCallback(async () => {
    if (searchQuery.trim()) {
      const filters: SearchFilters = {
        media: {},
      };

      // Convert filter options to search filters format
      if (filterOptions.mediaType?.types) {
        if (filterOptions.mediaType.types.video) {
          filters.media.video = ["*"];
        }
        if (filterOptions.mediaType.types.image) {
          filters.media.images = ["*"];
        }
        if (filterOptions.mediaType.types.audio) {
          filters.media.audio = ["*"];
        }
      }

      await refetch();
    }
  }, [searchQuery, filterOptions, refetch]);

  const handleLogout = useCallback(async () => {
    try {
      await signOut();
      StorageHelper.clearToken();
      setIsAuthenticated(false);
      navigate("/sign-in");
    } catch (error) {
      console.error("Error signing out:", error);
    }
  }, [navigate, setIsAuthenticated]);

  const handleChatToggle = useCallback(() => {
    setChatVisible((prev) => !prev);
  }, []);

  return {
    searchQuery,
    filterAnchorEl,
    filterOptions,
    setFilterOptions,
    chatVisible,
    handleSearchChange,
    handleFilterClick,
    handleFilterClose,
    handleSearchSubmit,
    handleLogout,
    handleChatToggle,
    handleDateChange,
  };
};
