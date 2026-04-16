import http from '@/utils/http'

// ─── Types ─────────────────────────────────────────────────────────────────────

/** 登录请求参数 */
export interface LoginRequest {
  email: string
  password: string
}

/** 登录成功响应类型 */
export interface LoginResponse {
  message: string
  email: string
  username: string
  role: 'user' | 'admin'
  access_token: string
}

export interface MeResponse {
  id: number
  email: string
  username: string
  role: 'user' | 'admin'
}

/** 注册请求参数 */
export interface RegisterRequest {
  email: string
  username: string
  password: string
  verificationCode: string
}

/** 注册成功响应 */
export interface RegisterResponse {
  message: string
  user: {
    id: string
    email: string
  }
}

export interface CaptchaRequest {
  email: string
}

export interface MessageResponse {
  message: string
}

/** 重置密码请求参数 */
export interface ResetPasswordRequest {
  email: string
  newpassword: string
  verificationCode: string
}

// ─── API Methods ───────────────────────────────────────────────────────────────

/**
 * 登录
 * POST /auth/login
 * 200 成功 | 400 邮箱或密码错误 | 500 服务器内部错误
 */
export function login(payload: LoginRequest) {
  return http.post<LoginResponse>('/auth/login', payload)
}

/**
 * 获取当前用户
 * GET /auth/me
 */
export function getCurrentUser() {
  return http.get<MeResponse>('/auth/me')
}

/**
 * 注册
 * POST /auth/register
 * 200 成功 | 400 参数错误 | 409 邮箱已存在 | 422 验证码错误
 */
export function register(payload: RegisterRequest) {
  return http.post<RegisterResponse>('/auth/register', payload)
}

/**
 * 发送注册验证码
 * POST /auth/register/captcha
 * 200 成功 | 400 邮箱格式错误
 */
export function sendRegisterCode(payload: CaptchaRequest) {
  return http.post<MessageResponse>('/auth/register/captcha', payload)
}

/**
 * 重置密码
 * POST /auth/password/reset
 * 200 成功 | 422 验证码错误
 */
export function resetPassword(payload: ResetPasswordRequest) {
  return http.post<MessageResponse>('/auth/password/reset', payload)
}

/**
 * 发送重置密码验证码
 * POST /auth/password/captcha
 * 200 成功 | 400 邮箱格式错误或不存在
 */
export function sendResetPasswordCode(payload: CaptchaRequest) {
  return http.post<MessageResponse>('/auth/password/captcha', payload)
}
