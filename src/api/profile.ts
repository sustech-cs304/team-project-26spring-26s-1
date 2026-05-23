import http from '@/utils/http'

export interface ProfileWriteResponse {
    [key: string]: never
}

export interface ProfileUpdateResponse {
    [key: string]: never
}

export function writeProfile(content: string): Promise<ProfileWriteResponse> {
    const formData = new FormData()
    formData.append('content', content)
    return http.post<ProfileWriteResponse>('/profile/write', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    })
}

export function updateProfile(): Promise<ProfileUpdateResponse> {
    return http.post<ProfileUpdateResponse>('/profile/update')
}
