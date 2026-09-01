export interface ApiError {
  message: string;
  detail?: string;
  status_code: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SelectOption {
  value: string;
  label: string;
}
