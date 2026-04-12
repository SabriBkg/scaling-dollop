export * from "./account";
export * from "./auth";

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
