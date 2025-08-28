import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient"; // Corrected import name
import { AWSRegion } from "@/api/types/api.types"; // Assuming you have this type or will create it

// Define the expected response structure from the API
interface GetAWSRegionsResponse {
  message: string;
  data: {
    regions: AWSRegion[];
  };
}

// Function to fetch AWS regions
const fetchAWSRegions = async (): Promise<GetAWSRegionsResponse> => {
  const { data } = await apiClient.get<GetAWSRegionsResponse>("/aws/regions"); // Use apiClient
  return data;
};

// Custom hook using react-query
export const useGetAWSRegions = (): UseQueryResult<AWSRegion[], Error> => {
  return useQuery<GetAWSRegionsResponse, Error, AWSRegion[]>({
    // Specify the selected type (AWSRegion[]) as the third generic
    queryKey: ["awsRegions"], // Unique key for caching
    queryFn: fetchAWSRegions,
    staleTime: Infinity, // Regions don't change often, cache indefinitely
    gcTime: Infinity, // Corrected property name (cacheTime -> gcTime)
    refetchOnWindowFocus: false, // No need to refetch on window focus
    refetchOnMount: false, // Only fetch once initially
    select: (data) => data.data.regions, // Select only the regions array for the hook's return value
  });
};
