<template>
    <v-layout class="h-100">

        <!-- 对话列表侧边栏 -->
        <v-navigation-drawer v-model="drawer" permanent width="250">
            <v-list nav density="compact">
                <!-- 新对话按钮 -->
                <v-list-item title="新对话" @click="newConversation" rounded="lg" slim prepend-gap="6" :ripple="false"
                    to="/c">
                    <template #prepend>
                        <v-icon size="x-small">mdi-chat-plus-outline</v-icon>
                    </template>
                </v-list-item>
                <!-- 搜索对话按钮 -->
                <v-list-item title="搜索对话历史" @click="searchConversations" link rounded="lg" slim prepend-gap="6"
                    :ripple="false">
                    <template #prepend>
                        <v-icon size="x-small">mdi-text-box-search-outline</v-icon>
                    </template>
                </v-list-item>
            </v-list>
            <v-divider></v-divider>
            <div class="d-flex align-center justify-space-between px-0 pt-2 pr-2">
                <v-card-subtitle>历史对话</v-card-subtitle>
            </div>
            <v-list nav density="compact">
                <v-list-item v-for="conv in conversations" :key="conv.id" :subtitle="conv.title" :to="`/c/${conv.id}`"
                    rounded="lg" color="primary" slim prepend-gap="6" :ripple="false">
                    <template #prepend>
                        <v-icon size="x-small">mdi-message-text-outline</v-icon>
                    </template>
                </v-list-item>
            </v-list>
        </v-navigation-drawer>

        <!-- 顶部应用栏 -->
        <v-app-bar flat height="48">
            <template #prepend>
                <v-btn :icon="drawer ? 'mdi-menu-open' : 'mdi-menu'" variant="text" @click="drawer = !drawer"
                    :ripple="false" size="x-small" />
                <v-btn icon="mdi-chat-plus-outline" @click="newConversation" size="x-small" variant="text"
                    v-if="!isStartPage" :ripple="false"></v-btn>
            </template>
            <v-btn @click="editTitle" text :ripple="false" v-if="!isStartPage" class="title-btn">{{ currentTitle }}
                <template #append>
                    <v-icon size="x-small" class="edit-icon">mdi-pencil-outline</v-icon>
                </template>
            </v-btn>
            <template #append>
                <v-btn icon="mdi-share" size="x-small" variant="text" :ripple="false" v-if="!isStartPage"></v-btn>
            </template>
        </v-app-bar>


        <!-- 子路由内容区 -->
        <v-main>
            <RouterView />
        </v-main>
    </v-layout>
</template>

<script setup lang="ts">
    const router = useRouter()
    const drawer = ref(true)

    const conversations = ref([
        { id: '1', title: '对话 1' },
        { id: '2', title: '对话 2' },
        { id: '123', title: '对话 123' },
    ])

    const route = useRoute()
    const currentTitle = computed(() => {
        // 外层 /c/ 拿不到子路由参数，通过当前路径从列表中匹配
        const conv = conversations.value.find(c => route.path === `/c/${c.id}`)
        return conv?.title ?? '新对话'
    })

    const isStartPage = computed(() => route.path === '/c/' || route.path === '/c')

    const newConversation = () => {
        // TODO: route to /c/
        router.push('/c/')
    }


    const editTitle = () => {
        // TODO: 编辑标题逻辑
    }

    const searchConversations = () => {
        alert('搜索对话历史功能待实现')
    }
</script>

<style scoped>
    .title-btn .edit-icon {
        opacity: 0;
        transition: opacity 0.15s ease;
    }

    .title-btn:hover .edit-icon {
        opacity: 1;
    }
</style>
