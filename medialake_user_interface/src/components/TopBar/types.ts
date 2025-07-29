export interface ChatMessage {
  text: string;
  sender: "user" | "assistant";
}

export interface FilterSectionType {
  types: {
    [key: string]: boolean;
  };
}

export interface CreationDateFilter {
  enabled: boolean;
  before: Date | null;
  after: Date | null;
}

export interface FilterOptions {
  mediaType: FilterSectionType;
  status: FilterSectionType;
  creationDate: CreationDateFilter;
}
