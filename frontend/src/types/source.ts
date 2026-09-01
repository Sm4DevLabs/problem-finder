// TypeScript interface matching the FastAPI response
export interface Source {
  id: string;
  name: string;
  source_type: string;
  homepage_url: string | null;
  collection_method: string | null;
  assessment_status: string | null;
  created_at: string;
  updated_at: string;
}

// Utility functions to format enum values for display
export const formatSourceType = (sourceType: string): string => {
  return sourceType
    .split("_")
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
};

export const formatCollectionMethod = (method: string | null): string => {
  if (!method) return "Not specified";
  return method
    .split("_")
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
};

export const formatAssessmentStatus = (status: string | null): string => {
  if (!status) return "Unknown";
  return status.charAt(0) + status.slice(1).toLowerCase();
};
