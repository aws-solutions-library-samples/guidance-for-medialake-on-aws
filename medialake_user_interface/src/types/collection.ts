export interface Collection {
  id: string;
  name: string;
  description: string;
  thumbnailType?: "icon" | "upload" | "asset" | "frame";
  thumbnailValue?: string;
  thumbnailUrl?: string;
  itemCount: number;
  collectionTypeId?: string;
  createdAt: string;
  lastModified: string;
}
