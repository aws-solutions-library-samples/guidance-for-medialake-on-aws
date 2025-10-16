export interface Collection {
  id: string;
  name: string;
  description: string;
  thumbnailUrl?: string;
  itemCount: number;
  collectionTypeId?: string;
  createdAt: string;
  lastModified: string;
}
