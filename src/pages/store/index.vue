<template>
    <v-container fluid class="bg-background px-6 px-md-10 pt-10 pb-12" style="min-height: 100vh;">
        <v-sheet class="mb-6 border-b" color="transparent">
            <div class="d-flex flex-wrap align-end justify-space-between ga-6">
                <div>
                    <div class="d-flex align-center ga-4">
                        <h1 class="text-h3 font-weight-black">Store</h1>
                    </div>
                    <p class="text-body-2 mt-3 mb-0 text-medium-emphasis" style="max-width: 420px; line-height: 1.65">
                        探索适合你的 OpenCrab Skill
                    </p>
                </div>

                <v-sheet rounded="xl" class="px-5 py-4 text-right" style="min-width: 172px; background: transparent">
                    <div class="text-primary font-weight-bold mb-2" style="font-size: clamp(2.1rem, 4.6vw, 3.3rem); line-height: 0.95">
                        {{ currentStatCount }}
                    </div>
                    <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase" style="letter-spacing: 0.14em">
                        {{ currentStatLabel }}
                    </div>
                </v-sheet>
            </div>
        </v-sheet>

        <v-sheet rounded="xl" class="mb-4 px-4 py-3" style="background: transparent">
            <div class="d-flex flex-wrap align-center ga-3">
                <v-tabs v-model="currentTab" color="primary" class="flex-grow-0">
                    <v-tab value="store">技能商店</v-tab>
                    <v-tab value="mySubmissions">我的投稿</v-tab>
                </v-tabs>

                <v-spacer />

                <v-text-field
                    v-model="search"
                    placeholder="Search skills..."
                    density="comfortable"
                    hide-details
                    variant="outlined"
                    prepend-inner-icon="mdi-magnify"
                    rounded="lg"
                    style="min-width: min(100%, 320px); max-width: 420px; flex: 0 1 420px"
                />

                <div class="d-flex align-center ga-3">
                    <v-btn
                        color="primary"
                        variant="flat"
                        rounded="lg"
                        prepend-icon="mdi-upload"
                        @click="openUploadDialog"
                    >
                        上传技能
                    </v-btn>

                    <v-btn
                        variant="outlined"
                        rounded="lg"
                        prepend-icon="mdi-refresh"
                        :loading="loading"
                        @click="loadCurrentTabData"
                    >
                        刷新
                    </v-btn>
                </div>
            </div>
        </v-sheet>

        <v-sheet
            v-if="currentTab === 'store'"
            rounded="xl"
            class="mb-6 px-4 py-4"
            style="background: transparent"
        >
            <div class="d-flex flex-wrap ga-3">
                <v-chip
                    v-for="tag in categoryOptions"
                    :key="tag.value ?? 'all'"
                    :color="activeTagId === tag.value ? 'primary' : ''"
                    :variant="activeTagId === tag.value ? 'tonal' : 'outlined'"
                    class="font-weight-bold px-4 py-2"
                    style="letter-spacing: 0.05em; font-size: 0.78rem"
                    link
                    @click="activeTagId = tag.value"
                >
                    {{ tag.label }}
                </v-chip>
            </div>
        </v-sheet>

        <v-sheet color="transparent">
            <v-alert
                v-if="apiMessage"
                class="mb-4"
                :type="apiMessageType"
                variant="tonal"
                density="comfortable"
            >
                {{ apiMessage }}
            </v-alert>

            <v-progress-linear
                v-if="loading"
                class="mb-4"
                color="primary"
                indeterminate
            />

            <template v-if="currentTab === 'store'">
                <v-row v-if="skills.length">
                    <v-col v-for="skill in skills" :key="skill.id" cols="12" sm="6" lg="4" xl="3">
                        <SkillCard
                            :title="skill.name"
                            :description="skill.description"
                            :tags="skill.tagNames"
                            :downloads="skill.download_count"
                            @click="openDetail(skill)"
                        >
                            <template #top-right>
                                <v-chip
                                    size="small"
                                    rounded="lg"
                                    :color="skill.install ? 'success' : 'default'"
                                    :variant="skill.install ? 'tonal' : 'outlined'"
                                >
                                    {{ getInstallStatusText(skill.install) }}
                                </v-chip>
                            </template>

                            <template #bottom-right>
                                <v-btn
                                    size="small"
                                    :color="skill.install ? 'error' : 'primary'"
                                    :variant="skill.install ? 'outlined' : 'flat'"
                                    rounded="lg"
                                    :loading="actionSkillId === skill.id && actionMode === getSkillActionMode(skill)"
                                    @click.stop="handleSkillAction(skill)"
                                >
                                    {{ skill.install ? '卸载' : '下载' }}
                                </v-btn>
                            </template>
                        </SkillCard>
                    </v-col>
                </v-row>

                <v-sheet
                    v-else-if="!loading"
                    rounded="xl"
                    class="pa-8 text-center text-medium-emphasis"
                    style="background: rgba(var(--v-theme-surface), 0.55);"
                >
                    暂无符合条件的技能
                </v-sheet>

                <div class="d-flex justify-center mt-8">
                    <v-pagination
                        v-model="page"
                        :length="totalPages"
                        rounded="lg"
                        density="comfortable"
                        total-visible="7"
                    />
                </div>
            </template>

            <template v-else-if="currentTab === 'mySubmissions'">
                <v-row v-if="filteredMySkills.length">
                    <v-col v-for="skill in filteredMySkills" :key="skill.id" cols="12" sm="6" lg="4" xl="3">
                        <SkillCard
                            :title="skill.name"
                            :description="skill.description"
                            :tags="skill.tags.map(t => t.name)"
                            :downloads="skill.download_count"
                            @click="openMySubmissionDetail(skill)"
                        >
                            <template #top-right>
                                <v-chip
                                    size="small"
                                    rounded="lg"
                                    :color="getMySkillStatusColor(skill.status)"
                                    variant="tonal"
                                >
                                    {{ getMySkillStatusText(skill.status) }}
                                </v-chip>
                            </template>

                            <template #bottom-right>
                                <v-btn
                                    size="small"
                                    color="error"
                                    variant="outlined"
                                    rounded="lg"
                                    :loading="deletingSubmissionId === skill.id"
                                    @click.stop="promptDeleteSubmission(skill)"
                                >
                                    删除投稿
                                </v-btn>
                            </template>
                        </SkillCard>
                    </v-col>
                </v-row>

                <v-sheet
                    v-else-if="!loading"
                    rounded="xl"
                    class="pa-8 text-center text-medium-emphasis"
                    style="background: rgba(var(--v-theme-surface), 0.55);"
                >
                    暂无投稿记录
                </v-sheet>
            </template>
        </v-sheet>

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
            <v-card rounded="xl">
                <v-card-title class="text-h6 font-weight-bold px-6 pt-6 pb-2">
                    删除投稿
                </v-card-title>
                <v-card-text class="px-6 py-4">
                    确认删除投稿" {{ pendingDeleteSkill?.name ?? '' }}" 吗？
                    这将下架该 Skill 且操作无法恢复。
                </v-card-text>
                <v-card-actions class="px-6 pb-6 pt-2">
                    <v-spacer />
                    <v-btn variant="text" :disabled="deletingSubmissionId !== null" @click="closeDeleteDialog">
                        取消
                    </v-btn>
                    <v-btn
                        size="small"
                        color="error"
                        variant="flat"
                        :loading="pendingDeleteSkill !== null && deletingSubmissionId === pendingDeleteSkill.id"
                        @click="confirmDeleteSubmission"
                    >
                        删除
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="downloadErrorDialogOpen" max-width="480">
            <v-card rounded="xl">
                <v-card-title class="text-h6 font-weight-bold px-6 pt-6 pb-2">
                    下载失败
                </v-card-title>
                <v-card-text class="px-6 py-4">
                    {{ downloadErrorMessage }}
                </v-card-text>
                <v-card-actions class="px-6 pb-6 pt-2">
                    <v-spacer />
                    <v-btn color="primary" variant="flat" @click="downloadErrorDialogOpen = false">
                        我知道了
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog v-model="actionSuccessDialogOpen" max-width="480">
            <v-card rounded="xl">
                <v-card-text class="px-6 py-4">
                    {{ actionSuccessMessage }}
                </v-card-text>
                <v-card-actions class="px-6 pb-6 pt-2">
                    <v-spacer />
                    <v-btn color="primary" variant="flat" @click="actionSuccessDialogOpen = false">
                        我知道了
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </v-container>
</template>

<script setup lang="ts">
    import { computed, onMounted, ref, watch } from 'vue'
    import type { AxiosError } from 'axios'
    import MySubmissionDetailDialog from '@/components/store/MySubmissionDetailDialog.vue'
    import SkillCard from '@/components/store/SkillCard.vue'
    import SkillDetailDialog from '@/components/store/SkillDetailDialog.vue'
    import UploadSkillDialog from '@/components/store/UploadSkillDialog.vue'
    import {
        deleteMySkill,
        getMySkills,
        getSkillDetail,
        getSkills,
        getTags,
        triggerSkillDownload,
        triggerSkillUninstall,
        uploadSkill,
    } from '@/api/store'
    import { useAuthStore } from '@/stores/auth'
    import type { StoreMySkill, StoreSkillDetail, StoreSkillSummary, StoreTag } from '@/types/store'

    type StoreSkillCard = StoreSkillSummary & {
        tagNames: string[]
    }

    type StoreActionSkill = StoreSkillCard | StoreSkillDetail

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
    const currentTab = ref<'store' | 'mySubmissions'>('store')
    const skills = ref<StoreSkillCard[]>([])
    const skillsTotal = ref(0)
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
    const authStore = useAuthStore()

    const detailActionLoading = computed(() =>
        selectedSkill.value !== null && actionSkillId.value === selectedSkill.value.id,
    )

    const filteredMySkills = computed(() => {
        const visibleSkills = mySkills.value.filter(skill => skill.status !== 'archived')
        const keyword = search.value.trim().toLowerCase()
        if (!keyword) return visibleSkills

        return visibleSkills.filter((skill) => {
            return skill.name.toLowerCase().includes(keyword)
                || skill.description.toLowerCase().includes(keyword)
                || skill.tags.some(tag => tag.name.toLowerCase().includes(keyword))
        })
    })

    const currentStatCount = computed(() =>
        currentTab.value === 'store' ? skillsTotal.value : filteredMySkills.value.length,
    )

    const currentStatLabel = computed(() =>
        currentTab.value === 'store' ? 'SKILLS COUNT' : 'MY SUBMISSIONS',
    )

    const categoryOptions = computed(() => [
        { label: 'ALL', value: null as number | null },
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

        if (tab === 'store') {
            if (page.value !== 1) {
                page.value = 1
                return
            }

            await loadStoreSkills()
        } else {
            page.value = 1
            await loadMySubmissionSkills()
        }
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
            tagNames: skill.tags.length ? skill.tags.map(tag => tag.name) : ['UNTAGGED'],
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
            const response = await getSkills({
                page: page.value,
                page_size: pageSize,
                tag_id: activeTagId.value ?? undefined,
                search: keyword || undefined,
            })

            skills.value = response.skills.map(toCardSkill)
            skillsTotal.value = response.total
        } catch (error) {
            skills.value = []
            skillsTotal.value = 0
            setApiMessage(`加载技能列表失败：${getErrorMessage(error)}`, 'error')
        } finally {
            loading.value = false
        }
    }

    async function loadMySubmissionSkills() {
        loading.value = true
        apiMessage.value = ''

        try {
            mySkills.value = await getMySkills()
        } catch (error) {
            mySkills.value = []
            if (isUnauthorizedError(error)) {
                setApiMessage('请先登录后查看投稿记录', 'warning')
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
        } else {
            await loadMySubmissionSkills()
        }
    }

    async function checkSubmissionLimit() {
        const authenticated = await authStore.ensureAuthenticated()
        if (!authenticated) {
            setApiMessage('请先登录后再上传技能', 'warning')
            return false
        }

        try {
            mySkills.value = await getMySkills()
        } catch (error) {
            if (isUnauthorizedError(error)) {
                setApiMessage('请先登录后再上传技能', 'warning')
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
        detailOpen.value = true
        detailLoading.value = true
        selectedSkill.value = null

        try {
            selectedSkill.value = await getSkillDetail(skill.id)
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
    :deep(.v-pagination .v-btn) {
        border-radius: 10px !important;
        background: rgba(var(--v-theme-surface), 0.88);
        color: rgb(var(--v-theme-on-surface));
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }

    :deep(.v-pagination .v-btn--active) {
        background: rgba(var(--v-theme-primary), 0.13);
        border-color: rgba(var(--v-theme-primary), 0.65);
        color: rgb(var(--v-theme-primary));
    }
</style>
