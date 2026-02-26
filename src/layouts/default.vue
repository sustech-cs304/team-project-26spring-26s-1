<template>
    <v-layout class="rounded rounded-md border">
        <v-app-bar color="surface-variant" title="Application bar"></v-app-bar>

        <v-navigation-drawer>
            <v-list nav>
                <v-list-item title="Drawer left" link></v-list-item>
            </v-list>
        </v-navigation-drawer>

        <v-navigation-drawer location="right">
            <v-list nav>
                <v-list-item title="Drawer right" link></v-list-item>
            </v-list>
        </v-navigation-drawer>

        <v-main>
            <router-view />
        </v-main>
    </v-layout>
</template>
<script lang="ts" setup>
    //
</script>