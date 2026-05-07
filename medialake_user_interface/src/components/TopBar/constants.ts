import { FilterOptions } from "./types";

export const INITIAL_FILTER_OPTIONS: FilterOptions = {
  mediaType: {
    types: {
      image: false,
      video: false,
      audio: false,
    },
  },
  status: {
    types: {
      pending: false,
      processed: false,
      failed: false,
    },
  },
  creationDate: {
    enabled: false,
    before: null,
    after: null,
  },
};
