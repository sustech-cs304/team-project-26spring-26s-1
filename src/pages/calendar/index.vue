<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 头部 -->
        <v-sheet class="px-6 py-4 border-b flex-shrink-0" color="transparent">
            <div class="d-flex align-center justify-space-between">
                <!-- 左侧 -->
                <div class="d-flex align-center ga-3">
                    <v-icon size="20" color="primary">mdi-calendar</v-icon>
                    <div>
                        <div class="text-h6 font-weight-bold" style="font-size:18px;line-height:1.3;">My Calendar</div>
                        <div class="text-caption text-medium-emphasis">{{ currentMonthLabel }}</div>
                    </div>
                </div>
                <!-- 右侧导航 -->
                <div class="d-flex align-center ga-1">
                    <v-btn icon variant="text" size="small" width="32" height="32" @click="prevWeek">
                        <v-icon size="16">mdi-chevron-left</v-icon>
                    </v-btn>
                    <v-btn variant="outlined" size="small" style="font-size:12px;height:28px;" @click="goToday">
                        Today
                    </v-btn>
                    <v-btn icon variant="text" size="small" width="32" height="32" @click="nextWeek">
                        <v-icon size="16">mdi-chevron-right</v-icon>
                    </v-btn>
                </div>
            </div>
        </v-sheet>

        <!-- 周日期条 -->
        <v-sheet class="border-b flex-shrink-0" color="transparent">
            <div class="d-flex">
                <div v-for="day in weekDays" :key="day.key" class="week-day-col"
                    :class="{ 'week-day-col--active': day.isSelected }" @click="selectedDate = day.date">
                    <span class="week-day-abbr">{{ day.abbr }}</span>
                    <div class="week-day-num-wrap" :class="{ 'week-day-num-wrap--active': day.isSelected }">
                        <span class="week-day-num" :class="{ 'week-day-num--active': day.isSelected }">{{ day.num
                            }}</span>
                    </div>
                    <span v-if="day.hasEvents" class="event-dot"
                        :class="day.isSelected ? 'event-dot--active' : 'event-dot--default'" />
                    <span v-else style="height:4px;" />
                </div>
            </div>
        </v-sheet>

        <!-- 事件列表 -->
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <div class="pa-6">
                <div class="text-body-2 font-weight-bold mb-4">{{ selectedDateLabel }} Events</div>

                <!-- 空状态 -->
                <div v-if="selectedDayEvents.length === 0" class="d-flex flex-column align-center justify-center py-12">
                    <v-icon size="32" style="opacity:0.4;" class="text-medium-emphasis mb-2">mdi-calendar-blank</v-icon>
                    <span class="text-body-2 text-medium-emphasis">No events for this day</span>
                </div>

                <!-- 事件卡片列表 -->
                <div v-else class="d-flex flex-column ga-3">
                    <div v-for="event in selectedDayEvents" :key="event.id" class="event-card"
                        :class="`event-card--${event.type}`">
                        <div class="d-flex ga-3">
                            <!-- 图标容器 -->
                            <div class="event-icon-wrap flex-shrink-0" :class="`event-icon-wrap--${event.type}`">
                                <v-icon size="16" :color="eventTypeColor(event.type)">{{ eventTypeIcon(event.type)
                                    }}</v-icon>
                            </div>
                            <!-- 信息区 -->
                            <div class="flex-grow-1 min-width-0">
                                <!-- 第一行：标题 + 类型标签 -->
                                <div class="d-flex align-center ga-1 flex-wrap">
                                    <span class="text-body-2 font-weight-medium text-truncate">{{ event.title }}</span>
                                    <v-chip variant="outlined" size="x-small" density="compact"
                                        :color="eventTypeColor(event.type)" style="font-size:9px;height:18px;">
                                        {{ event.type }}
                                    </v-chip>
                                </div>
                                <!-- 第二行：时间 & 地点 -->
                                <div class="d-flex align-center flex-wrap ga-3 mt-1">
                                    <span class="d-flex align-center ga-1">
                                        <v-icon size="12" class="text-medium-emphasis">mdi-clock-outline</v-icon>
                                        <span class="text-caption text-medium-emphasis">{{ event.time }}</span>
                                    </span>
                                    <span v-if="event.location" class="d-flex align-center ga-1">
                                        <v-icon size="12" class="text-medium-emphasis">mdi-map-marker-outline</v-icon>
                                        <span class="text-caption text-medium-emphasis">{{ event.location }}</span>
                                    </span>
                                </div>
                                <!-- 第三行：课程号 -->
                                <div v-if="event.courseId" class="text-medium-emphasis mt-1" style="font-size:10px;">
                                    Course: {{ event.courseId }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </v-sheet>

    </v-container>
</template>

<script setup lang="ts">
    type EventType = 'exam' | 'class' | 'personal' | 'deadline'

    interface CalEvent {
        id: number
        title: string
        type: EventType
        time: string
        date: string   // YYYY-MM-DD
        location?: string
        courseId?: string
    }

    const today = new Date()
    const selectedDate = ref(today)

    // 当前周起始（周日 = 0）
    const weekStart = computed(() => {
        const d = new Date(selectedDate.value)
        d.setDate(d.getDate() - d.getDay())
        return d
    })

    const weekDays = computed(() => {
        const abbrs = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        return Array.from({ length: 7 }, (_, i) => {
            const d = new Date(weekStart.value)
            d.setDate(d.getDate() + i)
            const key = d.toISOString().slice(0, 10)
            return {
                key,
                date: d,
                abbr: abbrs[i],
                num: d.getDate(),
                isSelected: key === selectedDate.value.toISOString().slice(0, 10),
                hasEvents: events.value.some(e => e.date === key),
            }
        })
    })

    const currentMonthLabel = computed(() => {
        return selectedDate.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    })

    const selectedDateLabel = computed(() => {
        return selectedDate.value.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    })

    const selectedDayEvents = computed(() => {
        const key = selectedDate.value.toISOString().slice(0, 10)
        return events.value.filter(e => e.date === key)
    })

    const prevWeek = () => {
        const d = new Date(selectedDate.value)
        d.setDate(d.getDate() - 7)
        selectedDate.value = d
    }
    const nextWeek = () => {
        const d = new Date(selectedDate.value)
        d.setDate(d.getDate() + 7)
        selectedDate.value = d
    }
    const goToday = () => { selectedDate.value = new Date() }

    // 颜色映射
    const eventTypeColor = (type: EventType) => ({
        exam: 'error', class: 'primary', personal: 'info', deadline: 'warning',
    }[type])

    const eventTypeIcon = (type: EventType) => ({
        exam: 'mdi-book-open-outline', class: 'mdi-calendar', personal: 'mdi-calendar', deadline: 'mdi-clock-alert-outline',
    }[type])

    // 示例数据（基于今天动态生成日期）
    const todayStr = today.toISOString().slice(0, 10)
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1)
    const tomorrowStr = tomorrow.toISOString().slice(0, 10)

    const events = ref<CalEvent[]>([
        { id: 1, title: 'Software Engineering Lecture', type: 'class', time: '08:00 - 09:50', date: todayStr, location: 'Teaching Building 1, Room 201', courseId: 'CS304' },
        { id: 2, title: 'Algorithm Midterm Exam', type: 'exam', time: '10:00 - 12:00', date: todayStr, location: 'Gym Hall A', courseId: 'CS302' },
        { id: 3, title: 'Project Submission Deadline', type: 'deadline', time: '23:59', date: todayStr, courseId: 'CS304' },
        { id: 4, title: 'Study Group Meeting', type: 'personal', time: '14:00 - 16:00', date: todayStr, location: 'Library Room B204' },
        { id: 5, title: 'Linear Algebra Lecture', type: 'class', time: '08:00 - 09:50', date: tomorrowStr, location: 'Teaching Building 2, Room 101', courseId: 'MA201' },
        { id: 6, title: 'Database Assignment Due', type: 'deadline', time: '23:59', date: tomorrowStr, courseId: 'CS307' },
    ])
</script>

<style scoped>

    /* 周日期条 */
    .week-day-col {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 12px 0;
        cursor: pointer;
        transition: background 0.15s;
    }

    .week-day-col:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5);
    }

    .week-day-col--active {
        background: rgba(var(--v-theme-primary), 0.1);
    }

    .week-day-abbr {
        font-size: 10px;
        text-transform: uppercase;
        color: rgba(var(--v-theme-on-surface), 0.6);
        letter-spacing: 0.05em;
    }

    .week-day-num-wrap {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .week-day-num-wrap--active {
        background: rgb(var(--v-theme-primary));
    }

    .week-day-num {
        font-size: 14px;
        font-weight: 500;
    }

    .week-day-num--active {
        color: #fff;
        font-weight: 600;
    }

    .event-dot {
        width: 4px;
        height: 4px;
        border-radius: 50%;
        display: inline-block;
    }

    .event-dot--default {
        background: rgb(var(--v-theme-primary));
    }

    .event-dot--active {
        background: #fff;
    }

    /* 事件卡片 */
    .event-card {
        border-radius: 12px;
        border: 1px solid;
        padding: 16px;
        transition: background 0.15s;
        cursor: pointer;
    }

    .event-card:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5) !important;
    }

    .event-card--exam {
        border-color: rgba(var(--v-theme-error), 0.3);
        background: rgba(var(--v-theme-error), 0.05);
    }

    .event-card--class {
        border-color: rgba(var(--v-theme-primary), 0.3);
        background: rgba(var(--v-theme-primary), 0.05);
    }

    .event-card--personal {
        border-color: rgba(var(--v-theme-info), 0.3);
        background: rgba(var(--v-theme-info), 0.05);
    }

    .event-card--deadline {
        border-color: rgba(var(--v-theme-warning), 0.3);
        background: rgba(var(--v-theme-warning), 0.05);
    }

    /* 事件图标容器 */
    .event-icon-wrap {
        width: 40px;
        height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .event-icon-wrap--exam {
        background: rgba(var(--v-theme-error), 0.1);
    }

    .event-icon-wrap--class {
        background: rgba(var(--v-theme-primary), 0.1);
    }

    .event-icon-wrap--personal {
        background: rgba(var(--v-theme-info), 0.1);
    }

    .event-icon-wrap--deadline {
        background: rgba(var(--v-theme-warning), 0.1);
    }
</style>
