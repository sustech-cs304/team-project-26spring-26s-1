<template>
    <v-layout class="h-100">

        <!-- 对话列表侧边栏 -->
        <v-navigation-drawer v-model="drawer" permanent width="250">
            <v-list nav density="compact" v-if="!searchMode">
                <!-- 新对话按钮 -->
                <v-list-item title="新对话" @click="newConversation" rounded="lg" slim prepend-gap="6" :ripple="false"
                    to="/c">
                    <template #prepend>
                        <v-icon size="small">mdi-chat-plus-outline</v-icon>
                    </template>
                </v-list-item>
                <!-- 搜索对话按钮 -->
                <v-list-item title="搜索对话历史" @click="enterSearchMode" link rounded="lg" slim prepend-gap="6"
                    :ripple="false">
                    <template #prepend>
                        <v-icon size="small">mdi-text-box-search-outline</v-icon>
                    </template>
                </v-list-item>
            </v-list>

            <!-- 搜索框 -->
            <div v-else class="px-2 py-2">
                <v-text-field v-model="searchKeyword" placeholder="搜索..." variant="outlined" density="compact"
                    hide-details clearable autofocus prepend-inner-icon="mdi-magnify" @click:clear="exitSearchMode"
                    @keydown.esc="exitSearchMode"></v-text-field>
                <div class="d-flex justify-end mt-1">
                    <v-btn size="x-small" variant="text" @click="exitSearchMode">取消</v-btn>
                </div>
            </div>

            <v-divider></v-divider>
            <div class="d-flex align-center justify-space-between px-0 pt-2 pr-2">
                <v-card-subtitle>{{ searchMode ? '搜索结果' : '历史对话' }}</v-card-subtitle>
            </div>

            <!-- Loading State -->
            <div v-if="loading" class="d-flex justify-center py-4">
                <v-progress-circular indeterminate size="24" color="primary"></v-progress-circular>
            </div>

            <v-list nav density="compact" v-else-if="displayConversations.length > 0">
                <v-list-item v-for="conv in displayConversations" :key="conv.conversation_id" :title="conv.title"
                    :to="`/c/${conv.conversation_id}`" rounded="lg" color="primary" slim prepend-gap="6" :ripple="false"
                    class="conv-item">
                    <template #prepend>
                        <v-icon size="x-small" v-if="conv.is_pinned && !searchMode" color="primary">mdi-pin</v-icon>
                    </template>
                    <template #append>
                        <v-menu :close-on-content-click="true" location="end">
                            <template #activator="{ props: menuProps }">
                                <v-btn v-bind="menuProps" icon="mdi-dots-vertical" size="x-small" variant="text"
                                    :ripple="false" class="conv-menu-btn" @click.prevent.stop />
                            </template>
                            <v-list density="compact" min-width="120" nav slim tile>
                                <v-list-item slim density="compact" :title="conv.is_pinned ? '取消置顶' : '置顶'"
                                    @click="handleTogglePin(conv)">
                                    <template #prepend>
                                        <v-icon size="x-small">{{ conv.is_pinned ? 'mdi-pin-off-outline' :
                                            'mdi-pin-outline' }}</v-icon>
                                    </template>
                                </v-list-item>
                                <v-list-item title="重命名" slim density="compact" @click="handleRename(conv)" height="10">
                                    <template #prepend>
                                        <v-icon size="x-small">mdi-pencil-outline</v-icon>
                                    </template>
                                </v-list-item>
                                <v-divider />
                                <v-list-item slim density="compact" title="删除" base-color="error"
                                    @click="handleDelete(conv)">
                                    <template #prepend>
                                        <v-icon size="x-small">mdi-delete-outline</v-icon>
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                    </template>
                </v-list-item>
            </v-list>

            <!-- Empty State -->
            <div v-else class="text-center py-4 text-body-medium opacity-70">
                {{ searchMode ? '未找到相关对话' : '暂无对话' }}
            </div>

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
        <v-app-bar flat height="48" color="transparent">
            <template #prepend>
                <v-btn :icon="drawer ? 'mdi-menu-open' : 'mdi-menu'" variant="text" @click="drawer = !drawer"
                    :ripple="false" size="small" />
                <v-btn icon="mdi-chat-plus-outline" @click="newConversation" size="small" variant="text"
                    v-if="!isStartPage" :ripple="false"></v-btn>
            </template>
            <v-btn @click="currentConversation && handleRename(currentConversation)" text :ripple="false"
                v-if="!isStartPage" class="title-btn">{{
                    currentTitle }}
                <template #append>
                    <v-icon size="x-small" class="edit-icon">mdi-pencil-outline</v-icon>
                </template>
            </v-btn>
            <template #append>
                <v-btn icon="mdi-share" size="small" variant="text" :ripple="false" v-if="!isStartPage"></v-btn>
            </template>
        </v-app-bar>


        <!-- 子路由内容区 -->
        <v-main scrollable>
            <RouterView />
        </v-main>

        <!-- 全屏拖拽上传遮罩层 -->
        <Teleport to="body">
            <Transition name="drop-fade">
                <div v-if="showDropZone" class="drop-overlay">
                    <div class="drop-overlay__content">
                        <v-icon icon="mdi-cloud-upload-outline" size="64" color="primary" />
                        <div class="text-h6 mt-4">拖拽文件到此处上传</div>
                        <div class="text-body-2 text-medium-emphasis mt-1">
                            支持图片、PDF、PPT、Markdown、TXT，单个文件不超过 5 MB
                        </div>
                        <div class="text-caption text-disabled mt-2">
                            上传的文件将缓存在本地，随对话删除自动清除
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>
    </v-layout>
</template>

<script setup lang="ts">
    import {
        getConversations,
        searchConversations,
        deleteConversation,
        updateConversation
    } from '@/api/conversation'
    import type { Conversation } from '@/types/conversation'
    import { debounce } from 'lodash'
    import { useAppStore } from '@/stores/app'

    const router = useRouter()
    const route = useRoute()
    const appStore = useAppStore()
    const drawer = ref(true)
    const loading = ref(false)

    // ── 拖拽上传（布局层统一管理） ─────────────
    /** 当前活跃子路由注册的 MessageInput 引用 */
    const messageInputRef = shallowRef<{ addFiles: (files: FileList | File[]) => void } | null>(null)
    const showDropZone = ref(false)
    let dragCounter = 0

    /** 子路由挂载时调用，注册 MessageInput 的 addFiles 方法 */
    const registerMessageInput = (ref: typeof messageInputRef.value) => {
        messageInputRef.value = ref
    }
    /** 子路由卸载时调用，清除引用 */
    const unregisterMessageInput = () => {
        messageInputRef.value = null
    }

    provide('registerMessageInput', registerMessageInput)
    provide('unregisterMessageInput', unregisterMessageInput)

    const onDragEnter = (e: DragEvent) => {
        e.preventDefault()
        if (e.dataTransfer?.types.includes('Files')) {
            dragCounter++
            showDropZone.value = true
        }
    }

    const onDragOver = (e: DragEvent) => {
        e.preventDefault()
    }

    const onDragLeave = (e: DragEvent) => {
        e.preventDefault()
        dragCounter--
        if (dragCounter <= 0) {
            dragCounter = 0
            showDropZone.value = false
        }
    }

    const onDrop = (e: DragEvent) => {
        e.preventDefault()
        dragCounter = 0
        showDropZone.value = false
        const files = e.dataTransfer?.files
        if (files && files.length > 0 && messageInputRef.value) {
            messageInputRef.value.addFiles(files)
        }
    }

    onMounted(() => {
        document.addEventListener('dragenter', onDragEnter)
        document.addEventListener('dragover', onDragOver)
        document.addEventListener('dragleave', onDragLeave)
        document.addEventListener('drop', onDrop)
        fetchConversations()
    })

    onBeforeUnmount(() => {
        document.removeEventListener('dragenter', onDragEnter)
        document.removeEventListener('dragover', onDragOver)
        document.removeEventListener('dragleave', onDragLeave)
        document.removeEventListener('drop', onDrop)
    })

    // Conversations state
    const conversations = ref<Conversation[]>([])
    const searchResults = ref<Conversation[]>([])

    // Search mode
    const searchMode = ref(false)
    const searchKeyword = ref('')

    // Display conversations based on mode
    const displayConversations = computed(() => {
        if (searchMode.value) {
            return searchResults.value
        }
        // Sort conversations: pinned first, then by updated_at (desc)
        return [...conversations.value].sort((a, b) => {
            if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
            return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        })
    })

    // Load conversations list
    const fetchConversations = async () => {
        loading.value = true
        try {
            const res = await getConversations({ page: 1, pageSize: 50 })
            conversations.value = res.conversations || []
        } catch (error) {
            console.error('Failed to fetch conversations:', error)
        } finally {
            loading.value = false
        }
    }

    // 监听 SSE set_title 事件：直接更新本地列表，无需重新请求接口
    watch(() => appStore.conversationTitleUpdate, (update) => {
        if (!update) return
        const conv = conversations.value.find(c => c.conversation_id === update.conversation_id)
        if (conv) {
            conv.title = update.title
        } else {
            // 新对话首次出现，刷新列表使其显示在侧边栏
            fetchConversations()
        }
    })

    // Search logic with debounce
    const performSearch = debounce(async (keyword: string) => {
        if (!keyword.trim()) {
            searchResults.value = []
            return
        }
        loading.value = true
        try {
            const res = await searchConversations({ keywords: keyword, page: 1, page_size: 50 })
            // Handle inconsistent backend response (conversations vs sessions)
            searchResults.value = res.conversations || []
        } catch (error) {
            console.error('Search failed:', error)
        } finally {
            loading.value = false
        }
    }, 500)

    watch(searchKeyword, (val) => {
        if (searchMode.value) {
            performSearch(val)
        }
    })

    const enterSearchMode = () => {
        searchMode.value = true
        searchKeyword.value = ''
        searchResults.value = []
    }

    const exitSearchMode = () => {
        searchMode.value = false
        searchKeyword.value = ''
        searchResults.value = []
        // Refresh original list in case something changed
        fetchConversations()
    }

    // Rename (Client-side only for now as no API provided)
    const renameDialog = ref(false)
    const renameValue = ref('')
    const renamingConv = ref<Conversation | null>(null)

    const handleRename = (conv: Conversation) => {
        renamingConv.value = conv
        renameValue.value = conv.title
        renameDialog.value = true
    }

    const confirmRename = async () => {
        if (renamingConv.value && renameValue.value.trim()) {
            const newTitle = renameValue.value.trim()
            // Optimistic update
            const oldTitle = renamingConv.value.title
            renamingConv.value.title = newTitle

            try {
                await updateConversation(renamingConv.value.conversation_id, { title: newTitle })
            } catch (error) {
                // Revert on failure
                if (renamingConv.value) renamingConv.value.title = oldTitle
                console.error('Rename failed:', error)
            }
        }
        renameDialog.value = false
    }

    // Pin
    const handleTogglePin = async (conv: Conversation) => {
        const newStatus = !conv.is_pinned
        // Optimistic update
        conv.is_pinned = newStatus
        try {
            await updateConversation(conv.conversation_id, { is_pinned: newStatus })
        } catch (error) {
            // Revert on failure
            conv.is_pinned = !newStatus
            console.error('Pin failed:', error)
        }
    }

    // Delete
    const handleDelete = async (conv: Conversation) => {
        if (!confirm(`确定要删除对话 "${conv.title}" 吗？`)) return

        try {
            await deleteConversation(conv.conversation_id)
            // Remove from list
            const idx = conversations.value.findIndex(c => c.conversation_id === conv.conversation_id)
            if (idx !== -1) conversations.value.splice(idx, 1)

            // Also remove from search results if valid
            if (searchMode.value) {
                const sIdx = searchResults.value.findIndex(c => c.conversation_id === conv.conversation_id)
                if (sIdx !== -1) searchResults.value.splice(sIdx, 1)
            }

            // Redirect if current
            if (route.path === `/c/${conv.conversation_id}`) {
                router.push('/c/')
            }
        } catch (error) {
            console.error('Delete failed:', error)
        }
    }

    const currentConversation = computed(() =>
        conversations.value.find(c => route.path === `/c/${c.conversation_id}`)
    )

    // Fallback title logic looks at conversations list
    const currentTitle = computed(() => {
        if (route.path === '/c/' || route.path === '/c') return '新的对话'
        return currentConversation.value ? currentConversation.value.title : '未知对话'
    })

    const isStartPage = computed(() => route.path === '/c/' || route.path === '/c')

    const newConversation = () => {
        router.push('/c/')
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

<!-- 非 scoped：Teleport 传送到 body 下的遮罩层样式 -->
<style>
    .drop-overlay {
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(var(--v-theme-surface), 0.85);
        backdrop-filter: blur(4px);
    }

    .drop-overlay__content {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 48px;
        border: 3px dashed rgb(var(--v-theme-primary));
        border-radius: 16px;
    }

    .drop-fade-enter-active,
    .drop-fade-leave-active {
        transition: opacity 0.2s ease;
    }

    .drop-fade-enter-from,
    .drop-fade-leave-to {
        opacity: 0;
    }
</style>
