import axios from 'axios'
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

const defaultBaseURL = import.meta.env.PROD ? 'http://127.0.0.1:8000' : '/api'
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? defaultBaseURL

/** 通用响应类型 */
export type ApiResponse<T = unknown> = {
  message: string
  data?: T
}

/** 创建 axios 实例 */
const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

/** 请求拦截器 —— 注入 token */
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('accessToken')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

/** 响应拦截器 —— 统一错误处理 */
http.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const message =
      error.response?.data?.message || error.message || 'Request failed'
    return Promise.reject(new Error(message))
  },
)

export default http