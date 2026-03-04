import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'

// Define the response structure based on standard API patterns
// Since the doc shows different structures, we try to keep it generic or follow the doc's wrapper if any.
// The doc shows direct JSON responses like { conversations: [] } or { message: "success" }.
// Sometimes APIs wrap data in { code: 200, data: ..., msg: ... }, but the provided doc 
// implies direct return of data in the body corresponding to 200 OK.

const http: AxiosInstance = axios.create({
    // Use environment variable for base URL, default to empty string (relative path) or specific API path
    baseURL: import.meta.env.VITE_API_BASE_URL || 'https://m1.apifoxmock.com/m1/7865145-7614648-default/',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request Interceptor
http.interceptors.request.use(
    (config) => {
        // TODO: Add token if authentication is implemented
        // const token = localStorage.getItem('token')
        // if (token) {
        //   config.headers.Authorization = `Bearer ${token}`
        // }
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
