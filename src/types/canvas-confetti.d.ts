declare module 'canvas-confetti' {
    export interface Options {
        particleCount?: number
        angle?: number
        spread?: number
        startVelocity?: number
        decay?: number
        gravity?: number
        drift?: number
        ticks?: number
        scalar?: number
        colors?: string[]
        origin?: {
            x?: number
            y?: number
        }
        zIndex?: number
        disableForReducedMotion?: boolean
    }

    export interface CreateOptions {
        resize?: boolean
        useWorker?: boolean
    }

    export type ConfettiInstance = (options?: Options) => Promise<null> | null

    interface ConfettiFn extends ConfettiInstance {
        create(canvas?: HTMLCanvasElement | null, options?: CreateOptions): ConfettiInstance
        reset(): void
    }

    const confetti: ConfettiFn
    export default confetti
}
