export * from "./account";

export type ApiResponse<T> = {
  data: T;
  message?: string;
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    field: string | null;
  };
};
