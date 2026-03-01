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
                    rounded="lg" color="primary" slim prepend-gap="6" :ripple="false" class="conv-item">
                    <template #prepend>
                        <v-icon size="x-small">mdi-message-text-outline</v-icon>
                    </template>
                    <template #append>
                        <v-menu :close-on-content-click="true" location="end">
                            <template #activator="{ props: menuProps }">
                                <v-btn v-bind="menuProps" icon="mdi-dots-vertical" size="x-small" variant="text"
                                    :ripple="false" class="conv-menu-btn" @click.prevent.stop />
                            </template>
                            <v-list density="compact" min-width="120" nav slim tile>
                                <v-list-item title="重命名" slim density="compact" @click="renameConversation(conv)"
                                    height="10">
                                    <template #prepend>
                                        <v-icon size="x-small">mdi-pencil-outline</v-icon>
                                    </template>
                                </v-list-item>
                                <v-list-item slim density="compact" :title="conv.pinned ? '取消置顶' : '置顶'"
                                    @click="togglePin(conv)">
                                    <template #prepend>
                                        <v-icon size="x-small">{{ conv.pinned ? 'mdi-pin-off-outline' :
                                            'mdi-pin-outline' }}</v-icon>
                                    </template>
                                </v-list-item>
                                <v-divider />
                                <v-list-item slim density="compact" title="删除" base-color="error"
                                    @click="deleteConversation(conv)">
                                    <template #prepend>
                                        <v-icon size="x-small">mdi-delete-outline</v-icon>
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                    </template>
                </v-list-item>
            </v-list>

            <!-- 重命名对话框 -->
            <v-dialog v-model="renameDialog" max-width="360">
                <v-card title="重命名对话">
                    <v-card-text>
                        <v-text-field v-model="renameValue" label="对话名称" autofocus variant="outlined" density="compact"
                            @keyup.enter="confirmRename" />
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer />
                        <v-btn variant="text" @click="renameDialog = false">取消</v-btn>
                        <v-btn variant="tonal" color="primary" @click="confirmRename">确认</v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
        </v-navigation-drawer>

        <!-- 顶部应用栏 -->
        <v-app-bar flat height="48">
            <template #prepend>
                <v-btn :icon="drawer ? 'mdi-menu-open' : 'mdi-menu'" variant="text" @click="drawer = !drawer"
                    :ripple="false" size="x-small" />
                <v-btn icon="mdi-chat-plus-outline" @click="newConversation" size="x-small" variant="text"
                    v-if="!isStartPage" :ripple="false"></v-btn>
            </template>
            <v-btn @click="currentConversation && renameConversation(currentConversation)" text :ripple="false"
                v-if="!isStartPage" class="title-btn">{{
                    currentTitle }}
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
        { id: '1', title: '对话 1', pinned: false },
        { id: '2', title: '对话 2', pinned: false },
        { id: '123', title: '对话 123', pinned: false },
    ])

    // 重命名
    const renameDialog = ref(false)
    const renameValue = ref('')
    const renamingConv = ref<{ id: string; title: string; pinned: boolean } | null>(null)

    const renameConversation = (conv: { id: string; title: string; pinned: boolean }) => {
        renamingConv.value = conv
        renameValue.value = conv.title
        renameDialog.value = true
    }

    const confirmRename = () => {
        if (renamingConv.value && renameValue.value.trim()) {
            renamingConv.value.title = renameValue.value.trim()
        }
        renameDialog.value = false
    }

    // 置顶
    const togglePin = (conv: { id: string; title: string; pinned: boolean }) => {
        conv.pinned = !conv.pinned
    }

    // 删除
    const deleteConversation = (conv: { id: string; title: string; pinned: boolean }) => {
        const idx = conversations.value.findIndex(c => c.id === conv.id)
        if (idx !== -1) conversations.value.splice(idx, 1)
        if (route.path === `/c/${conv.id}`) router.push('/c/')
    }

    const route = useRoute()
    const currentConversation = computed(() => conversations.value.find(c => route.path === `/c/${c.id}`))
    const currentTitle = computed(() => {
        if (route.path === '/c/' || route.path === '/c') return '新的对话'
        return currentConversation.value ? currentConversation.value.title : '未知对话'
    })

    const isStartPage = computed(() => route.path === '/c/' || route.path === '/c')

    const newConversation = () => {
        // TODO: route to /c/
        router.push('/c/')
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

    .conv-item .conv-menu-btn {
        opacity: 0;
        transition: opacity 0.15s ease;
    }

    .conv-item:hover .conv-menu-btn {
        opacity: 1;
    }
</style>
