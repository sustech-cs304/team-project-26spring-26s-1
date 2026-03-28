import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'

/** 统一的 API 根地址，去除末尾斜杠，供 fetch 等场景复用 */
const defaultBaseURL = import.meta.env.PROD
    ? 'http://127.0.0.1:8000/'
    : 'https://m1.apifoxmock.com/m1/7865145-7614648-default'

export const baseURL = ((import.meta.env.VITE_API_BASE_URL as string) || defaultBaseURL).replace(/\/+$/, '')

const http: AxiosInstance = axios.create({
    baseURL,
    timeout: 10000,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request Interceptor
http.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem('accessToken')
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Response Interceptor
http.interceptors.response.use(
    (response: AxiosResponse) => {
        return response.data
    },
    (error: AxiosError) => {
        // Handle errors
        if (error.response) {
            switch (error.response.status) {
                case 401:
                    console.error('Unauthorized, please login.')
                    break
                case 403:
                    console.error('Forbidden.')
                    break
                case 404:
                    console.error('Resource not found.')
                    break
                case 500:
                    console.error('Internal Server Error.')
                    break
                default:
                    console.error(`Error: ${error.response.status}`)
            }
        } else if (error.request) {
            console.error('No response received:', error.request)
        } else {
            console.error('Request error:', error.message)
        }
        return Promise.reject(error)
    }
)

/**
 * Generic request wrapper to fix return types
 */
const request = {
    get<T = any> (url: string, config?: AxiosRequestConfig): Promise<T> {
        return http.get(url, config) as Promise<T>
    },
    post<T = any> (url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.post(url, data, config) as Promise<T>
    },
    put<T = any> (url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.put(url, data, config) as Promise<T>
    },
    patch<T = any> (url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        return http.patch(url, data, config) as Promise<T>
    },
    delete<T = any> (url: string, config?: AxiosRequestConfig): Promise<T> {
        return http.delete(url, config) as Promise<T>
    }
}

export default request
