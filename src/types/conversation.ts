// conversation types

export type ThinkingStepStatus = 'running' | 'done' | 'error'
export type ThinkingStepType = 'search' | 'code' | 'tool' | 'read' | 'think' | 'api'


export interface ThinkingStep {
    id: string
    type: ThinkingStepType
    title: string
    content?: string
    status: ThinkingStepStatus
    time: string
}