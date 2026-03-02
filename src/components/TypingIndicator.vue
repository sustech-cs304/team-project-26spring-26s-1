<template>
    <v-row class="mb-4" density="compact">
        <v-col cols="auto">
            <v-sheet rounded="lg" color="transparent" class="px-3 py-2 d-flex align-center ga-2">
                <v-icon v-for="(delay, i) in [0, 150, 300]" :key="i" size="8" color="primary" class="dot-bounce"
                    :style="`animation-delay: ${delay}ms`">mdi-circle</v-icon>
            </v-sheet>
        </v-col>
    </v-row>
</template>

<style scoped>
    .dot-bounce {
        animation: bounce 1s ease-in-out infinite;
    }

    @keyframes bounce {

        0%,
        100% {
            transform: translateY(0);
            opacity: 0.4;
        }

        50% {
            transform: translateY(-4px);
            opacity: 1;
        }
    }
</style>
