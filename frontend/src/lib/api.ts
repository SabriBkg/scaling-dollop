/**
 * Configured axios instance for all SafeNet API calls.
 *
 * All API requests are routed through the Next.js API proxy at /api/proxy/,
 * which reads the httpOnly access cookie and forwards to Django with an
 * Authorization: Bearer header. This keeps tokens out of client-side JS.
 *
 * On 401: attempts silent token refresh via the server-side cookie bridge,
 * then retries the original request. On refresh failure: clears cookies
 * and redirects to /login.
 */

import axios from "axios";
import { clearTokens } from "./auth";

const api = axios.create({
  baseURL: "/api/proxy",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// Response interceptor — handle 401 with silent refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (err: unknown) => void;
}> = [];

const processQueue = (error: unknown) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(undefined);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // The refresh endpoint reads the httpOnly refresh cookie automatically
        await axios.post(
          "/api/auth/refresh",
          {},
          { withCredentials: true }
        );
        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        await clearTokens();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
