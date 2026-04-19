import http from '@/utils/http'

export interface PatchCasPayload {
    id?: string
    password?: string
}

export interface PatchCasResponse {
    message: string
}

export function patchCas(payload: PatchCasPayload): Promise<PatchCasResponse> {
    return http.patch<PatchCasResponse>('/patch_cas', payload)
}
