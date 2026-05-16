<template>
    <v-layout class="store-workspace h-100 overflow-hidden min-height-0">
        <v-app-bar flat height="48" color="background" class="store-app-bar">
            <template #prepend>
                <v-icon size="18" class="ml-3">mdi-connection</v-icon>
            </template>

            <div class="store-app-title">
                Store
            </div>

            <template #append>
                <div class="d-flex align-center ga-1 pr-2">
                    <v-tooltip text="上传技能" location="bottom">
                        <template #activator="{ props }">
                            <v-btn v-bind="props" icon="mdi-upload-outline" size="small" variant="text"
                                :ripple="false" @click="openUploadDialog" />
                        </template>
                    </v-tooltip>
                    <v-tooltip text="刷新" location="bottom">
                        <template #activator="{ props }">
                            <v-btn v-bind="props" icon="mdi-refresh" size="small" variant="text" :loading="loading"
                                :ripple="false" @click="loadCurrentTabData" />
                        </template>
                    </v-tooltip>
                </div>
            </template>
        </v-app-bar>

        <v-main class="store-main h-100 overflow-hidden min-height-0">
            <div class="store-route-panel">
                <div class="store-content-shell">
                    <div class="store-toolbar">
                        <v-tabs v-model="currentTab" class="store-tabs" density="compact" height="34">
                            <v-tab value="store" :ripple="false">技能商店</v-tab>
                            <v-tab value="downloaded" :ripple="false">已下载</v-tab>
                            <v-tab value="mySubmissions" :ripple="false">我的投稿</v-tab>
                        </v-tabs>

                        <div class="store-toolbar-controls">
                            <v-text-field v-model="search" placeholder="搜索技能" density="compact" hide-details
                                variant="solo-filled" flat prepend-inner-icon="mdi-magnify" clearable rounded="lg"
                                class="store-search" />
                            <v-chip size="small" rounded="lg" variant="tonal" class="store-count-chip">
                                {{ currentStatCount }} {{ currentStatLabel }}
                            </v-chip>
                        </div>
                    </div>

                    <div v-if="currentTab === 'store'" class="store-filter-row">
                        <v-chip v-for="tag in categoryOptions" :key="tag.value ?? 'all'"
                            :variant="activeTagId === tag.value ? 'tonal' : 'outlined'" size="small" rounded="lg"
                            :ripple="false" @click="activeTagId = tag.value">
                            {{ tag.label }}
                        </v-chip>
                    </div>

                    <v-alert v-if="apiMessage" class="mb-2" :type="apiMessageType" variant="tonal" density="compact"
                        rounded="lg">
                        {{ apiMessage }}

                        <template v-if="showLoginAction" #append>
                            <v-btn size="small" variant="text" @click="goToLogin">
                                去登录
                            </v-btn>
                        </template>
                    </v-alert>

                    <v-progress-linear v-if="loading" class="mb-2" indeterminate />

                    <div class="store-results">
                        <template v-if="currentTab === 'store'">
                            <v-row v-if="skills.length" dense>
                                <v-col v-for="skill in skills" :key="skill.id" cols="12" sm="6" lg="4" xl="3">
                                    <SkillCard :title="skill.name" :description="skill.description"
                                        :tags="skill.tagNames" :downloads="skill.download_count"
                                        @click="openDetail(skill)">
                                        <template #top-right>
                                            <v-chip size="x-small" rounded="lg"
                                                :variant="skill.install ? 'tonal' : 'outlined'">
                                                {{ getInstallStatusText(skill.install) }}
                                            </v-chip>
                                        </template>

                                        <template #bottom-right>
                                            <v-btn size="x-small" :variant="skill.install ? 'outlined' : 'tonal'"
                                                rounded="lg"
                                                :prepend-icon="skill.install ? 'mdi-trash-can-outline' : 'mdi-download-outline'"
                                                :loading="actionSkillId === skill.id && actionMode === getSkillActionMode(skill)"
                                                @click.stop="handleSkillAction(skill)">
                                                {{ skill.install ? '卸载' : '下载' }}
                                            </v-btn>
                                        </template>
                                    </SkillCard>
                                </v-col>
                            </v-row>

                            <div v-else-if="!loading" class="store-empty-state">
                                <v-icon size="22">mdi-package-variant-closed</v-icon>
                                <span>暂无符合条件的技能</span>
                            </div>

                            <div v-if="totalPages > 1" class="d-flex justify-center mt-3">
                                <v-pagination v-model="page" :length="totalPages" rounded="lg" density="compact"
                                    total-visible="7" />
                            </div>
                        </template>

                        <template v-else-if="currentTab === 'downloaded'">
                            <v-row v-if="filteredDownloadedSkills.length" dense>
                                <v-col v-for="skill in filteredDownloadedSkills" :key="skill.id" cols="12" sm="6"
                                    lg="4" xl="3">
                                    <SkillCard :title="skill.name" :description="skill.description"
                                        :tags="skill.tags.map(t => t.name)" :downloads="skill.download_count"
                                        @click="openDetail(skill)">
                                        <template #top-right>
                                            <v-chip size="x-small" rounded="lg" variant="tonal">
                                                已安装
                                            </v-chip>
                                        </template>

                                        <template #bottom-right>
                                            <v-btn size="x-small" variant="outlined" rounded="lg"
                                                prepend-icon="mdi-trash-can-outline"
                                                :loading="actionSkillId === skill.id && actionMode === 'remove'"
                                                @click.stop="removeSkill(skill)">
                                                卸载
                                            </v-btn>
                                        </template>
                                    </SkillCard>
                                </v-col>
                            </v-row>

                            <div v-else-if="!loading" class="store-empty-state">
                                <v-icon size="22">mdi-download-box-outline</v-icon>
                                <span>暂无已下载技能</span>
                            </div>
                        </template>

                        <template v-else-if="currentTab === 'mySubmissions'">
                            <v-row v-if="filteredMySkills.length" dense>
                                <v-col v-for="skill in filteredMySkills" :key="skill.id" cols="12" sm="6" lg="4" xl="3">
                                    <SkillCard :title="skill.name" :description="skill.description"
                                        :tags="skill.tags.map(t => t.name)" :downloads="skill.download_count"
                                        @click="openMySubmissionDetail(skill)">
                                        <template #top-right>
                                            <v-chip size="x-small" rounded="lg" :color="getMySkillStatusColor(skill.status)"
                                                variant="tonal">
                                                {{ getMySkillStatusText(skill.status) }}
                                            </v-chip>
                                        </template>

                                        <template #bottom-right>
                                            <v-btn size="x-small" color="error" variant="text" rounded="lg"
                                                prepend-icon="mdi-delete-outline"
                                                :loading="deletingSubmissionId === skill.id"
                                                @click.stop="promptDeleteSubmission(skill)">
                                                删除
                                            </v-btn>
                                        </template>
                                    </SkillCard>
                                </v-col>
                            </v-row>

                            <div v-else-if="!loading" class="store-empty-state">
                                <v-icon size="22">mdi-file-upload-outline</v-icon>
                                <span>暂无投稿记录</span>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </v-main>

        <SkillDetailDialog
            v-model="detailOpen"
            :skill="selectedSkill"
            :loading="detailLoading"
            :action-loading="detailActionLoading"
            @install="installSkill"
            @remove="removeSkill"
        />

        <MySubmissionDetailDialog
            v-model="mySubmissionDetailOpen"
            :skill="selectedMySubmission"
        />

        <UploadSkillDialog
            v-model="uploadDialogOpen"
            :loading="uploading"
            :tags="availableTags"
            @submit="handleUploadSkill"
        />

        <v-dialog v-model="deleteDialogOpen" max-width="420">
            <v-card rounded="lg">
                <v-card-title class="text-subtitle-1 font-weight-bold px-4 pt-4 pb-1">
                    删除投稿
                </v-card-title>
                <v-card-text class="px-4 py-3 text-body-2">
                    确认删除投稿「{{ pendingDeleteSkill?.name ?? '' }}」吗？
                    这将下架该 Skill 且操作无法恢复。
                </v-card-text>
                <v-card-actions class="px-4 pb-4 pt-1">
                    <v-spacer />
                    <v-btn size="small" variant="text" :disabled="deletingSubmissionId !== null" @click="closeDeleteDialog">
                        取消
                    </v-btn>
                    <v-btn size="small" color="error" variant="tonal"
                        :loading="pendingDeleteSkill !== null && deletingSubmissionId === pendingDeleteSkill.id"
                        @click="confirmDeleteSubmission">
                        删除
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="downloadErrorDialogOpen" max-width="480">
            <v-card rounded="lg">
                <v-card-title class="text-subtitle-1 font-weight-bold px-4 pt-4 pb-1">
                    下载失败
                </v-card-title>
                <v-card-text class="px-4 py-3 text-body-2">
                    {{ downloadErrorMessage }}
                </v-card-text>
                <v-card-actions class="px-4 pb-4 pt-1">
                    <v-spacer />
                    <v-btn size="small" variant="tonal" @click="downloadErrorDialogOpen = false">
                        我知道了
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="actionSuccessDialogOpen" max-width="480">
            <v-card rounded="lg">
                <v-card-text class="px-4 py-3 text-body-2">
                    {{ actionSuccessMessage }}
                </v-card-text>
                <v-card-actions class="px-4 pb-4 pt-1">
                    <v-spacer />
                    <v-btn size="small" variant="tonal" @click="actionSuccessDialogOpen = false">
                        我知道了
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </v-layout>
</template>

<script setup lang="ts">
    import { computed, onMounted, ref, watch } from 'vue'
    import type { AxiosError } from 'axios'
    import { useRouter } from 'vue-router'
    import MySubmissionDetailDialog from '@/components/store/MySubmissionDetailDialog.vue'
    import SkillCard from '@/components/store/SkillCard.vue'
    import SkillDetailDialog from '@/components/store/SkillDetailDialog.vue'
    import UploadSkillDialog from '@/components/store/UploadSkillDialog.vue'
    import {
        deleteMySkill,
        getDownloadedSkillDetail,
        getDownloadedSkills,
        getMySkills,
        getSkillDetail,
        getSkills,
        getTags,
        triggerSkillDownload,
        triggerSkillUninstall,
        uploadSkill,
    } from '@/api/store'
    import { useAuthStore } from '@/stores/auth'
    import { LOGIN_PATH } from '@/utils/authSession'
    import type {
        LocalDownloadedSkill,
        LocalDownloadedSkillDetail,
        StoreMySkill,
        StoreSkillDetail,
        StoreSkillSummary,
        StoreTag,
    } from '@/types/store'

    type StoreSkillCard = StoreSkillSummary & {
        tagNames: string[]
    }

    type DownloadedSkillCard = LocalDownloadedSkill & {
        id: number
        install: true
        download_count: number
        tags: StoreTag[]
    }

    type StoreActionSkill = StoreSkillCard | DownloadedSkillCard | StoreSkillDetail

    const MAX_MY_SUBMISSIONS = 5
    const pageSize = 20
    const search = ref('')
    const activeTagId = ref<number | null>(null)
    const page = ref(1)
    const loading = ref(false)
    const detailLoading = ref(false)
    const detailOpen = ref(false)
    const mySubmissionDetailOpen = ref(false)
    const apiMessage = ref('')
    const apiMessageType = ref<'info' | 'success' | 'warning' | 'error'>('info')
    const currentTab = ref<'store' | 'downloaded' | 'mySubmissions'>('store')
    const skills = ref<StoreSkillCard[]>([])
    const skillsTotal = ref(0)
    const downloadedSkills = ref<DownloadedSkillCard[]>([])
    const mySkills = ref<StoreMySkill[]>([])
    const uploadDialogOpen = ref(false)
    const uploading = ref(false)
    const deleteDialogOpen = ref(false)
    const downloadErrorDialogOpen = ref(false)
    const downloadErrorMessage = ref('')
    const actionSuccessDialogOpen = ref(false)
    const actionSuccessMessage = ref('')
    const availableTags = ref<StoreTag[]>([])
    const selectedSkill = ref<StoreSkillDetail | null>(null)
    const selectedMySubmission = ref<StoreMySkill | null>(null)
    const pendingDeleteSkill = ref<StoreMySkill | null>(null)
    const actionSkillId = ref<number | null>(null)
    const actionMode = ref<'install' | 'remove' | null>(null)
    const deletingSubmissionId = ref<number | null>(null)
    const showLoginAction = ref(false)
    const authStore = useAuthStore()
    const router = useRouter()

    const detailActionLoading = computed(() =>
        selectedSkill.value !== null && actionSkillId.value === selectedSkill.value.id,
    )

    const filteredMySkills = computed(() => {
        const keyword = search.value.trim().toLowerCase()
        if (!keyword) return mySkills.value

        return mySkills.value.filter((skill) => {
            return skill.name.toLowerCase().includes(keyword)
                || skill.description.toLowerCase().includes(keyword)
                || skill.tags.some(tag => tag.name.toLowerCase().includes(keyword))
        })
    })

    const filteredDownloadedSkills = computed(() => {
        const keyword = search.value.trim().toLowerCase()
        if (!keyword) return downloadedSkills.value

        return downloadedSkills.value.filter((skill) => {
            return skill.name.toLowerCase().includes(keyword)
                || skill.description.toLowerCase().includes(keyword)
                || skill.tags.some(tag => tag.name.toLowerCase().includes(keyword))
        })
    })

    const currentStatCount = computed(() =>
        currentTab.value === 'store'
            ? skillsTotal.value
            : currentTab.value === 'downloaded'
                ? filteredDownloadedSkills.value.length
                : filteredMySkills.value.length,
    )

    const currentStatLabel = computed(() =>
        currentTab.value === 'store'
            ? '个技能'
            : currentTab.value === 'downloaded'
                ? '个已下载'
                : '个投稿',
    )

    const categoryOptions = computed(() => [
        { label: '全部', value: null as number | null },
        ...availableTags.value.map(tag => ({ label: tag.name, value: tag.id })),
    ])

    const totalPages = computed(() => Math.max(1, Math.ceil(skillsTotal.value / pageSize)))

    watch([search, activeTagId], () => {
        if (currentTab.value !== 'store') return

        if (page.value !== 1) {
            page.value = 1
            return
        }

        void loadStoreSkills()
    })

    watch(page, () => {
        if (currentTab.value === 'store') {
            void loadStoreSkills()
        }
    })

    watch(totalPages, (value) => {
        if (page.value > value) {
            page.value = value
        }
    })

    watch(currentTab, async (tab) => {
        apiMessage.value = ''
        showLoginAction.value = false

        if (tab === 'store') {
            if (page.value !== 1) {
                page.value = 1
                return
            }

            await loadStoreSkills()
            return
        }

        page.value = 1

        if (tab === 'downloaded') {
            await loadDownloadedSkills()
            return
        }

        await loadMySubmissionSkills()
    })

    function getMySkillStatusText(status: string) {
        switch (status) {
            case 'pending': return '审核中'
            case 'approved': return '已上架'
            case 'rejected': return '已拒绝'
            case 'archived': return '已归档'
            default: return status
        }
    }

    function getMySkillStatusColor(status: string) {
        switch (status) {
            case 'pending': return 'warning'
            case 'approved': return 'success'
            case 'rejected': return 'error'
            case 'archived': return 'grey'
            default: return 'default'
        }
    }

    function getInstallStatusText(install: boolean) {
        return install ? '已安装' : '未安装'
    }

    function getSkillActionMode(skill: StoreActionSkill): 'install' | 'remove' {
        return skill.install ? 'remove' : 'install'
    }

    async function handleSkillAction(skill: StoreActionSkill) {
        if (skill.install) {
            await removeSkill(skill)
            return
        }

        await installSkill(skill)
    }

    function setApiMessage(message: string, type: typeof apiMessageType.value = 'info') {
        apiMessage.value = message
        apiMessageType.value = type
    }

    function goToLogin() {
        router.push({
            path: LOGIN_PATH,
            query: {
                returnTo: '/store',
            },
        })
    }

    function showDownloadErrorDialog(message: string) {
        downloadErrorMessage.value = message
        downloadErrorDialogOpen.value = true
    }

    function showActionSuccessDialog(message: string) {
        actionSuccessMessage.value = message
        actionSuccessDialogOpen.value = true
    }

    function getErrorMessage(error: unknown, fallback = '请求失败') {
        const axiosError = error as AxiosError<{ detail?: string, message?: string }>
        return axiosError.response?.data?.detail
            || axiosError.response?.data?.message
            || (error instanceof Error ? error.message : fallback)
    }

    function isUnauthorizedError(error: unknown) {
        const axiosError = error as AxiosError
        return axiosError.response?.status === 401
    }

    function toCardSkill(skill: StoreSkillSummary): StoreSkillCard {
        return {
            ...skill,
            tagNames: skill.tags.map(tag => tag.name),
        }
    }

    function toDownloadedSkillCard(skill: LocalDownloadedSkill): DownloadedSkillCard {
        return {
            ...skill,
            id: skill.cloud_skill_id,
            install: true,
            download_count: 0,
            tags: [],
        }
    }

    function toDownloadedSkillDetail(skill: LocalDownloadedSkillDetail): StoreSkillDetail {
        return {
            id: skill.cloud_skill_id,
            name: skill.name,
            description: skill.description,
            markdown_content: skill.markdown_content,
            install: true,
            download_count: 0,
            tags: [],
            created_at: '',
        }
    }

    function syncStoreSkillInstallState(downloadedList: LocalDownloadedSkill[] = downloadedSkills.value) {
        const downloadedSkillIds = new Set(downloadedList.map(skill => skill.cloud_skill_id))

        skills.value = skills.value.map(skill => ({
            ...skill,
            install: downloadedSkillIds.has(skill.id),
        }))

        if (selectedSkill.value) {
            selectedSkill.value = {
                ...selectedSkill.value,
                install: downloadedSkillIds.has(selectedSkill.value.id),
            }
        }
    }

    function updateSkillInstallState(skillId: number, install: boolean) {
        skills.value = skills.value.map(skill => (
            skill.id === skillId
                ? { ...skill, install }
                : skill
        ))

        if (selectedSkill.value?.id === skillId) {
            selectedSkill.value = {
                ...selectedSkill.value,
                install,
            }
        }
    }

    function incrementDownloadCount(skillId: number) {
        skills.value = skills.value.map(skill => (
            skill.id === skillId
                ? { ...skill, download_count: skill.download_count + 1 }
                : skill
        ))

        if (selectedSkill.value?.id === skillId) {
            selectedSkill.value = {
                ...selectedSkill.value,
                download_count: selectedSkill.value.download_count + 1,
            }
        }
    }

    async function loadTags() {
        try {
            availableTags.value = await getTags()
        } catch (error) {
            availableTags.value = []
            setApiMessage(`加载标签失败：${getErrorMessage(error)}`, 'warning')
        }
    }

    async function loadStoreSkills() {
        loading.value = true
        apiMessage.value = ''

        try {
            const keyword = search.value.trim()
            const [response, downloadedResponse] = await Promise.all([
                getSkills({
                    page: page.value,
                    page_size: pageSize,
                    tag_id: activeTagId.value ?? undefined,
                    search: keyword || undefined,
                }),
                getDownloadedSkills(),
            ])

            skills.value = response.skills.map(toCardSkill)
            skillsTotal.value = response.total

            if (downloadedResponse) {
                downloadedSkills.value = downloadedResponse.map(toDownloadedSkillCard)
                syncStoreSkillInstallState(downloadedResponse)
            } else {
                downloadedSkills.value = []
                syncStoreSkillInstallState([])
            }
        } catch (error) {
            skills.value = []
            skillsTotal.value = 0
            setApiMessage(`加载技能列表失败：${getErrorMessage(error)}`, 'error')
        } finally {
            loading.value = false
        }
    }

    async function loadDownloadedSkills(silent = false) {
        if (!silent) {
            loading.value = true
            apiMessage.value = ''
        }

        try {
            const response = await getDownloadedSkills()
            downloadedSkills.value = response.map(toDownloadedSkillCard)
            syncStoreSkillInstallState(response)
        } catch (error) {
            if (!silent) {
                downloadedSkills.value = []
                syncStoreSkillInstallState([])
                setApiMessage(`加载已下载技能失败：${getErrorMessage(error)}`, 'error')
            }
        } finally {
            if (!silent) {
                loading.value = false
            }
        }
    }

    async function loadMySubmissionSkills() {
        loading.value = true
        apiMessage.value = ''
        showLoginAction.value = false

        try {
            mySkills.value = await getMySkills()
        } catch (error) {
            mySkills.value = []
            if (isUnauthorizedError(error)) {
                setApiMessage('请先登录后查看投稿记录', 'warning')
                showLoginAction.value = true
                return
            }

            setApiMessage(`加载投稿记录失败：${getErrorMessage(error)}`, 'error')
        } finally {
            loading.value = false
        }
    }

    async function loadCurrentTabData() {
        if (currentTab.value === 'store') {
            await loadStoreSkills()
            return
        }

        if (currentTab.value === 'downloaded') {
            await loadDownloadedSkills()
            return
        }

        await loadMySubmissionSkills()
    }

    async function checkSubmissionLimit() {
        showLoginAction.value = false
        const authenticated = await authStore.ensureAuthenticated()
        if (!authenticated) {
            setApiMessage('请先登录后再上传技能', 'warning')
            showLoginAction.value = true
            return false
        }

        try {
            mySkills.value = await getMySkills()
        } catch (error) {
            if (isUnauthorizedError(error)) {
                setApiMessage('请先登录后再上传技能', 'warning')
                showLoginAction.value = true
                return false
            }

            setApiMessage(`校验投稿数量失败：${getErrorMessage(error)}`, 'error')
            return false
        }

        const activeSubmissionCount = mySkills.value.filter((skill) => skill.status !== 'archived').length

        if (activeSubmissionCount >= MAX_MY_SUBMISSIONS) {
            setApiMessage(`个人投稿最多 ${MAX_MY_SUBMISSIONS} 个技能，请先删除后再上传`, 'warning')
            return false
        }

        return true
    }

    async function openUploadDialog() {
        const canUpload = await checkSubmissionLimit()
        if (!canUpload) {
            uploadDialogOpen.value = false
            return
        }

        uploadDialogOpen.value = true
    }

    async function handleUploadSkill(payload: { file: File, tagIds: number[] }) {
        uploading.value = true

        try {
            const canUpload = await checkSubmissionLimit()
            if (!canUpload) {
                uploadDialogOpen.value = false
                return
            }

            await uploadSkill(payload.file, payload.tagIds)
            setApiMessage('上传成功，等待审核', 'success')
            uploadDialogOpen.value = false

            if (currentTab.value === 'mySubmissions') {
                await loadMySubmissionSkills()
            } else {
                currentTab.value = 'mySubmissions'
            }
        } catch (error) {
            setApiMessage(`上传失败：${getErrorMessage(error)}`, 'error')
        } finally {
            uploading.value = false
        }
    }

    async function openDetail(skill: StoreActionSkill) {
        const fromDownloadedTab = currentTab.value === 'downloaded'

        detailOpen.value = true
        detailLoading.value = true
        selectedSkill.value = null

        try {
            const detail = fromDownloadedTab
                ? toDownloadedSkillDetail(await getDownloadedSkillDetail(skill.id))
                : await getSkillDetail(skill.id)
            const downloadedSkillIds = new Set(downloadedSkills.value.map(item => item.id))
            selectedSkill.value = {
                ...detail,
                install: downloadedSkillIds.has(detail.id),
            }
        } catch (error) {
            setApiMessage(`加载技能详情失败：${getErrorMessage(error)}`, 'error')
        } finally {
            detailLoading.value = false
        }
    }

    function openMySubmissionDetail(skill: StoreMySkill) {
        selectedMySubmission.value = skill
        mySubmissionDetailOpen.value = true
    }

    function promptDeleteSubmission(skill: StoreMySkill) {
        pendingDeleteSkill.value = skill
        deleteDialogOpen.value = true
    }

    function closeDeleteDialog() {
        if (deletingSubmissionId.value !== null) return

        deleteDialogOpen.value = false
        pendingDeleteSkill.value = null
    }

    async function confirmDeleteSubmission() {
        const skill = pendingDeleteSkill.value
        if (!skill) return

        deletingSubmissionId.value = skill.id

        try {
            const response = await deleteMySkill(skill.id)
            deleteDialogOpen.value = false
            pendingDeleteSkill.value = null

            if (selectedMySubmission.value?.id === skill.id) {
                selectedMySubmission.value = null
                mySubmissionDetailOpen.value = false
            }

            await loadMySubmissionSkills()
            setApiMessage(response.message || `已删除：${skill.name}`, 'success')
        } catch (error) {
            setApiMessage(`删除失败：${getErrorMessage(error)}`, 'error')
        } finally {
            deletingSubmissionId.value = null
        }
    }

    async function installSkill(skill: StoreActionSkill | null) {
        if (!skill) return

        actionSkillId.value = skill.id
        actionMode.value = 'install'

        try {
            const response = await triggerSkillDownload(skill.id)
            updateSkillInstallState(response.skill_id, true)
            await loadDownloadedSkills(true)
            showActionSuccessDialog(response.message || `已下载：${skill.name}`)
            incrementDownloadCount(response.skill_id)
        } catch (error) {
            showDownloadErrorDialog(`下载失败：${getErrorMessage(error)}`)
        } finally {
            actionSkillId.value = null
            actionMode.value = null
        }
    }

    async function removeSkill(skill: StoreActionSkill | null) {
        if (!skill) return

        actionSkillId.value = skill.id
        actionMode.value = 'remove'

        try {
            const response = await triggerSkillUninstall(skill.id)
            updateSkillInstallState(response.skill_id, false)
            await loadDownloadedSkills(true)

            if (currentTab.value === 'downloaded' && selectedSkill.value?.id === response.skill_id) {
                detailOpen.value = false
                selectedSkill.value = null
            }

            showActionSuccessDialog(response.message || `已卸载：${skill.name}`)
        } catch (error) {
            setApiMessage(`卸载失败：${getErrorMessage(error)}`, 'error')
        } finally {
            actionSkillId.value = null
            actionMode.value = null
        }
    }

    onMounted(async () => {
        await loadTags()
        await loadStoreSkills()
    })
</script>

<style scoped>
    .store-workspace {
        --store-content-radius: 8px;
        background: rgb(var(--v-theme-surface));
    }

    .store-app-bar {
        background: rgb(var(--v-theme-background)) !important;
        border-top-left-radius: var(--store-content-radius) !important;
        overflow: hidden;
    }

    .store-app-bar :deep(.v-toolbar__content) {
        position: relative;
    }

    .store-app-title {
        position: absolute;
        left: 50%;
        overflow: hidden;
        font-size: 0.875rem;
        font-weight: 600;
        line-height: 1.25rem;
        text-overflow: ellipsis;
        transform: translateX(-50%);
        white-space: nowrap;
    }

    .store-main {
        background: transparent;
    }

    .store-route-panel {
        height: 100%;
        min-height: 0;
        overflow: hidden;
        background: rgb(var(--v-theme-background));
        border-bottom-left-radius: var(--store-content-radius);
    }

    .store-content-shell {
        height: 100%;
        min-height: 0;
        overflow-y: auto;
        padding: 12px 16px 16px;
    }

    .store-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: 36px;
    }

    .store-toolbar-controls {
        display: flex;
        flex: 1 1 auto;
        align-items: center;
        justify-content: flex-end;
        gap: 8px;
        min-width: 0;
    }

    .store-search {
        flex: 0 1 360px;
        max-width: 360px;
    }

    .store-search :deep(.v-field) {
        font-size: 0.8125rem;
    }

    .store-count-chip {
        flex-shrink: 0;
        font-weight: 600;
    }

    .store-filter-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding-block: 8px 10px;
    }

    .store-results {
        min-height: 0;
        padding-top: 8px;
    }

    .store-filter-row+.store-results {
        padding-top: 0;
    }

    .store-empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-height: 180px;
        color: rgba(var(--v-theme-on-surface), 0.58);
        font-size: 0.8125rem;
    }

    .store-tabs :deep(.v-tab) {
        min-width: auto;
        padding-inline: 12px;
        border-radius: 8px;
        font-size: 0.8125rem;
        font-weight: 600;
        letter-spacing: 0;
        text-transform: none;
    }

    .store-tabs :deep(.v-tab.v-tab--selected) {
        background: rgba(var(--v-theme-on-surface), 0.07);
        color: rgb(var(--v-theme-on-surface));
    }

    .store-tabs :deep(.v-tab__slider) {
        display: none;
    }

    .store-filter-row :deep(.v-chip) {
        font-weight: 600;
    }

    .store-filter-row :deep(.v-chip--variant-tonal) {
        background: rgba(var(--v-theme-on-surface), 0.08);
        color: rgb(var(--v-theme-on-surface));
    }

    :deep(.v-pagination .v-btn) {
        border-radius: 10px !important;
        background: rgba(var(--v-theme-on-surface), 0.04);
        color: rgb(var(--v-theme-on-surface));
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }

    :deep(.v-pagination .v-btn--active) {
        background: rgba(var(--v-theme-on-surface), 0.12);
        color: rgb(var(--v-theme-on-surface));
    }

    @media (max-width: 760px) {
        .store-toolbar {
            align-items: stretch;
            flex-direction: column;
        }

        .store-toolbar-controls {
            justify-content: stretch;
        }

        .store-search {
            max-width: none;
        }
    }
</style>
