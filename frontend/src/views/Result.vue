<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { message } from "ant-design-vue";

import AmapTripMap from "../components/AmapTripMap.vue";
import AssistantPanel from "../components/AssistantPanel.vue";
import {
  editTrip,
  exportTripMarkdown,
  exportTripPdf,
  fetchWeatherForecast,
  navigateBrowser,
  saveTrip,
} from "../services/api";
import { useItineraryStore } from "../stores/itinerary";
import type { CandidateItinerary, DayPlan, Itinerary, SourceType, WeatherForecastResponse } from "../types";

const itineraryStore = useItineraryStore();

const props = defineProps<{
  itinerary: Itinerary | null;
  mode?: "result" | "sources" | "agent-status";
}>();

const emit = defineEmits<{
  backHome: [];
  viewHistory: [];
}>();

const saving = ref(false);
const exportingPdf = ref(false);
const exportingMarkdown = ref(false);
const editing = ref(false);
const editScope = ref("day_1");
const editInstruction = ref("这一天节奏更轻松一点，减少固定安排。");
const weatherLoading = ref(false);
const weatherError = ref("");
const weather = ref<WeatherForecastResponse | null>(null);
const draggedDayIndex = ref<number | null>(null);
const pendingChangeType = ref("manual_save");
const viewMode = computed(() => props.mode || "result");
const isResultMode = computed(() => viewMode.value === "result");
const isSourcesMode = computed(() => viewMode.value === "sources");
const isAgentStatusMode = computed(() => viewMode.value === "agent-status");

const sourceTypeLabels: Record<SourceType, string> = {
  demo: "本地演示（仅供参考）",
  estimate: "规则估算（仅供参考）",
  user_input: "用户录入",
  tavily: "Tavily 检索（仅供参考）",
  official_api: "正式 API",
  browser_observed: "Browser 观察（仅供参考）",
};

function sourceLabel(sourceType?: SourceType | null): string {
  if (!sourceType) {
    return "未标记";
  }
  return sourceTypeLabels[sourceType] || sourceType;
}

function isNonRealtimeSource(sourceType?: SourceType | null): boolean {
  return (
    sourceType === "demo"
    || sourceType === "estimate"
    || sourceType === "tavily"
    || sourceType === "browser_observed"
  );
}

const sourceRecords = computed(() => props.itinerary?.source_records || []);
const candidateItineraries = computed(() => props.itinerary?.candidate_itineraries || []);
const agentEvents = computed(() => props.itinerary?.execution_events || []);

function formatShortDate(dateText?: string | null): string {
  if (!dateText) {
    return "待定";
  }

  const parts = dateText.split("-");
  if (parts.length !== 3) {
    return dateText;
  }

  return `${parts[1]}-${parts[2]}`;
}

function formatWeatherDate(dateText?: string | null, week?: string | null): string {
  const weekdayMap: Record<string, string> = {
    "1": "周一",
    "2": "周二",
    "3": "周三",
    "4": "周四",
    "5": "周五",
    "6": "周六",
    "7": "周日",
  };
  const weekday = week ? weekdayMap[week] || `周${week}` : "";
  return [formatShortDate(dateText), weekday].filter(Boolean).join(" ");
}

function firstCostSource<T extends { cost_source_type?: SourceType }>(items: T[]): SourceType | undefined {
  return (
    items.find((item) => item.cost_source_type === "browser_observed")?.cost_source_type
    || items.find((item) => item.cost_source_type)?.cost_source_type
  );
}

const budgetItems = computed(() => {
  if (!props.itinerary) {
    return [];
  }

  const budget = props.itinerary.budget_breakdown;
  const allSpots = props.itinerary.days.flatMap((day) => day.spots);
  const allMeals = props.itinerary.days.flatMap((day) => day.meals);
  const allTransport = props.itinerary.days.flatMap((day) => day.transport);
  const allHotels = props.itinerary.days.flatMap((day) => (day.hotel ? [day.hotel] : []));

  return [
    { label: "景点门票", value: `¥${budget.tickets.toFixed(0)}`, sourceType: firstCostSource(allSpots) || budget.source_type },
    { label: "酒店住宿", value: `¥${budget.hotel.toFixed(0)}`, sourceType: firstCostSource(allHotels) || budget.source_type },
    { label: "餐饮费用", value: `¥${budget.meals.toFixed(0)}`, sourceType: firstCostSource(allMeals) || budget.source_type },
    { label: "交通费用", value: `¥${budget.transport.toFixed(0)}`, sourceType: firstCostSource(allTransport) || budget.source_type },
  ];
});

const dayBudgetItems = computed(() => {
  if (!props.itinerary) {
    return [];
  }

  return props.itinerary.days.map((day) => {
    const tickets = day.spots.reduce((sum, spot) => sum + (spot.estimated_cost ?? 0), 0);
    const meals = day.meals.reduce((sum, meal) => sum + (meal.estimated_cost ?? 0), 0);
    const transport = day.transport.reduce((sum, item) => sum + (item.estimated_cost ?? 0), 0);
    const hotel = day.hotel?.estimated_cost ?? 0;
    const total = tickets + meals + transport + hotel;

    return {
      key: day.day_index,
      title: `第${day.day_index}天`,
      subtitle: day.theme || "未命名主题",
      tickets,
      meals,
      transport,
      hotel,
      total,
    };
  });
});

const mapPoints = computed(() => {
  if (!props.itinerary) {
    return [];
  }

  return props.itinerary.days.flatMap((day) =>
    day.spots.map((spot) => ({
      key: `${day.day_index}-${spot.name}`,
      dayIndex: day.day_index,
      date: day.date || "待定",
      theme: day.theme || "未命名主题",
      name: spot.name,
      address: spot.address || spot.location || "待补充",
      latitude: spot.latitude,
      longitude: spot.longitude,
      poiId: spot.poi_id,
      imageUrl: spot.image_url,
      description: spot.description || "暂无说明",
      sourceType: spot.source_type,
      costSourceType: spot.cost_source_type,
    }))
  );
});

const technicalTipKeywords = [
  "LLM",
  "RAG",
  "LangChain",
  "Chroma",
  "演示",
  "测试",
  "规则",
  "模型",
  "源码",
];

const rainWeatherKeywords = ["雨", "阵雨", "雷阵雨", "小雨", "中雨", "大雨"];
const sunnyTipKeywords = ["防晒", "太阳", "日照", "晒"];

const weatherText = computed(() => {
  if (!weather.value) {
    return "";
  }

  return weather.value.days
    .map((day) => `${day.day_weather || ""}${day.night_weather || ""}`)
    .join(" ");
});

const hasRainyWeather = computed(() => {
  return rainWeatherKeywords.some((keyword) => weatherText.value.includes(keyword));
});

const displayTips = computed(() => {
  if (!props.itinerary) {
    return [];
  }

  const tips = props.itinerary.tips
    .map((tip) => tip.trim())
    .filter(Boolean)
    .filter((tip) => !technicalTipKeywords.some((keyword) => tip.includes(keyword)));

  const weatherAwareTips = hasRainyWeather.value
    ? tips.filter((tip) => !sunnyTipKeywords.some((keyword) => tip.includes(keyword)))
    : tips;

  if (hasRainyWeather.value) {
    weatherAwareTips.push("天气可能有雨，建议随身带伞或轻便雨衣。");
    weatherAwareTips.push("阴雨天路面湿滑，洱海边和古镇石板路建议穿防滑鞋。");
  }

  const uniqueTips = Array.from(new Set(weatherAwareTips));
  if (uniqueTips.length) {
    return uniqueTips;
  }

  return [
    `建议根据${props.itinerary.destination}当天实时天气准备雨具或薄外套。`,
    "古镇、生态廊道和石板路更适合慢慢走，鞋子尽量选择舒适防滑的款式。",
  ];
});

function buildVisibleItinerary(): Itinerary | null {
  if (!props.itinerary) {
    return null;
  }

  return {
    ...props.itinerary,
    tips: displayTips.value,
  };
}

function recalculateBudget(itinerary: Itinerary): Itinerary {
  const transport = itinerary.days.reduce(
    (sum, day) => sum + day.transport.reduce((daySum, item) => daySum + (item.estimated_cost ?? 0), 0),
    0,
  );
  const hotel = itinerary.days.reduce((sum, day) => sum + (day.hotel?.estimated_cost ?? 0), 0);
  const meals = itinerary.days.reduce(
    (sum, day) => sum + day.meals.reduce((daySum, item) => daySum + (item.estimated_cost ?? 0), 0),
    0,
  );
  const tickets = itinerary.days.reduce(
    (sum, day) => sum + day.spots.reduce((daySum, item) => daySum + (item.estimated_cost ?? 0), 0),
    0,
  );
  const other = Math.max(0, Number(((transport + hotel + meals + tickets) * 0.06).toFixed(2)));
  const total = Number((transport + hotel + meals + tickets + other).toFixed(2));
  return {
    ...itinerary,
    estimated_budget: total,
    budget_breakdown: {
      transport: Number(transport.toFixed(2)),
      hotel: Number(hotel.toFixed(2)),
      meals: Number(meals.toFixed(2)),
      tickets: Number(tickets.toFixed(2)),
      other,
      total,
      source_type: "estimate",
    },
  };
}

function applyCandidate(candidate: CandidateItinerary) {
  if (!props.itinerary) {
    return;
  }
  pendingChangeType.value = "candidate_select";
  itineraryStore.set( {
    ...props.itinerary,
    summary: candidate.summary,
    days: candidate.days,
    estimated_budget: candidate.estimated_budget,
    budget_breakdown: candidate.budget_breakdown,
  });
  message.success(`已套用候选方案：${candidate.title}，保存后会生成新版本。`);
}

function handleDayDragStart(dayIndex: number) {
  draggedDayIndex.value = dayIndex;
}

function normalizeReorderedDays(days: DayPlan[]): DayPlan[] {
  return days.map((day, index) => ({
    ...day,
    day_index: index + 1,
    notes: Array.from(new Set([...(day.notes || []), "已通过拖拽调整日程顺序。"])),
  }));
}

function handleDayDrop(targetDayIndex: number) {
  if (!props.itinerary || draggedDayIndex.value === null || draggedDayIndex.value === targetDayIndex) {
    draggedDayIndex.value = null;
    return;
  }

  const days = props.itinerary.days.map((day) => ({ ...day }));
  const fromIndex = days.findIndex((day) => day.day_index === draggedDayIndex.value);
  const toIndex = days.findIndex((day) => day.day_index === targetDayIndex);
  if (fromIndex === -1 || toIndex === -1) {
    draggedDayIndex.value = null;
    return;
  }

  const [movedDay] = days.splice(fromIndex, 1);
  days.splice(toIndex, 0, movedDay);
  const updated = recalculateBudget({
    ...props.itinerary,
    days: normalizeReorderedDays(days),
  });
  pendingChangeType.value = "drag_edit";
  draggedDayIndex.value = null;
  itineraryStore.set( updated);
  message.success("日程顺序已调整，保存后会生成拖拽编辑版本。");
}

function openBlobExport(blob: Blob, filename: string, exportWindow: Window | null) {
  const blobUrl = URL.createObjectURL(blob);
  if (exportWindow) {
    exportWindow.location.href = blobUrl;
  } else {
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    link.click();
  }

  window.setTimeout(() => {
    URL.revokeObjectURL(blobUrl);
  }, 60000);
}

async function loadWeather() {
  if (!props.itinerary?.destination) {
    weather.value = null;
    return;
  }

  weatherLoading.value = true;
  weatherError.value = "";
  try {
    weather.value = await fetchWeatherForecast(props.itinerary.destination);
  } catch (error) {
    console.error(error);
    weather.value = null;
    weatherError.value = "天气信息加载失败。";
  } finally {
    weatherLoading.value = false;
  }
}

watch(
  () => props.itinerary?.destination,
  () => {
    void loadWeather();
  },
  { immediate: true }
);

watch(
  () => props.itinerary?.trip_id,
  () => {
    const firstDay = props.itinerary?.days[0];
    editScope.value = firstDay ? `day_${firstDay.day_index}` : "day_1";
  },
  { immediate: true }
);

async function openPdfExport() {
  const itineraryToExport = buildVisibleItinerary();
  if (!itineraryToExport) {
    return;
  }

  const exportWindow = window.open("about:blank", "_blank");
  exportingPdf.value = true;
  try {
    const saveResponse = await saveTrip(itineraryToExport);
    const exportTripId = saveResponse.trip_id;
    if (exportTripId !== itineraryToExport.trip_id) {
      itineraryStore.set( { ...itineraryToExport, trip_id: exportTripId });
    }
    const pdfBlob = await exportTripPdf(exportTripId);
    openBlobExport(pdfBlob, `${exportTripId}.pdf`, exportWindow);
  } catch (error) {
    console.error(error);
    exportWindow?.close();
    message.error("导出 PDF 前同步当前行程失败。");
  } finally {
    exportingPdf.value = false;
  }
}

async function openMarkdownExport() {
  const itineraryToExport = buildVisibleItinerary();
  if (!itineraryToExport) {
    return;
  }

  const exportWindow = window.open("about:blank", "_blank");
  exportingMarkdown.value = true;
  try {
    const saveResponse = await saveTrip(itineraryToExport);
    const exportTripId = saveResponse.trip_id;
    if (exportTripId !== itineraryToExport.trip_id) {
      itineraryStore.set( { ...itineraryToExport, trip_id: exportTripId });
    }
    const markdownBlob = await exportTripMarkdown(exportTripId);
    openBlobExport(markdownBlob, `${exportTripId}.md`, exportWindow);
  } catch (error) {
    console.error(error);
    exportWindow?.close();
    message.error("导出 Markdown 前同步当前行程失败。");
  } finally {
    exportingMarkdown.value = false;
  }
}

const navigateLoading = ref("");
const navigateError = ref("");

function getTripDates() {
  if (!props.itinerary) return { start: "", end: "" };
  const days = props.itinerary.days;
  return {
    start: days[0]?.date || "",
    end: days[days.length - 1]?.date || "",
  };
}

async function handleNavigate(category: "flight" | "train" | "hotel" | "vacation") {
  if (!props.itinerary) return;
  navigateLoading.value = category;
  navigateError.value = "";
  try {
    const dates = getTripDates();
    const result = await navigateBrowser({
      category,
      origin_city: props.itinerary.days[0]?.transport?.[0]?.from_place || "",
      destination: props.itinerary.destination,
      start_date: dates.start,
      end_date: dates.end,
    });
    message.success(result.message);
  } catch (error: any) {
    const detail = error?.response?.data?.detail || "浏览器启动失败";
    navigateError.value = detail;
    message.error(detail);
  } finally {
    navigateLoading.value = "";
  }
}

async function handleSave() {
  const itineraryToSave = buildVisibleItinerary();
  if (!itineraryToSave) {
    return;
  }

  saving.value = true;
  try {
    const saveResponse = await saveTrip(itineraryToSave, pendingChangeType.value);
    if (saveResponse.trip_id !== itineraryToSave.trip_id) {
      itineraryStore.set( { ...itineraryToSave, trip_id: saveResponse.trip_id });
    }
    pendingChangeType.value = "manual_save";
    message.success("行程已保存，可以去历史列表查看。");
  } catch (error) {
    console.error(error);
    message.error("保存行程失败。");
  } finally {
    saving.value = false;
  }
}

async function handleEdit() {
  if (!props.itinerary) {
    return;
  }

  const instruction = editInstruction.value.trim();
  if (!instruction) {
    message.warning("请先输入想如何调整行程。");
    return;
  }

  editing.value = true;
  try {
    const updatedItinerary = await editTrip({
      trip_id: props.itinerary.trip_id,
      current_itinerary: props.itinerary,
      user_instruction: instruction,
      edit_scope: editScope.value,
      preserve_constraints: ["保留预算结构", "保留目的地和旅行日期"],
    });
    itineraryStore.set( updatedItinerary);
    message.success("行程已智能调整。");
  } catch (error) {
    console.error(error);
    message.error("智能调整失败，请稍后再试。");
  } finally {
    editing.value = false;
  }
}

function handleAssistantUpdated(updatedItinerary: Itinerary, versionNumber?: number | null) {
  itineraryStore.set( updatedItinerary);
  if (versionNumber) {
    message.success(`AI 旅行顾问已生成版本 ${versionNumber}`);
  }
}
</script>

<template>
  <section v-if="itinerary" class="result-page">
    <aside class="sidebar-card">
      <div class="sidebar-card__title">
        {{ isSourcesMode ? "来源导航" : isAgentStatusMode ? "执行导航" : "行程导航" }}
      </div>
      <ul v-if="isResultMode" class="sidebar-list">
        <li>行程概览</li>
        <li>预算明细</li>
        <li>按天花费</li>
        <li>智能调整</li>
        <li>景点地图</li>
        <li>天气信息</li>
        <li>点位明细</li>
        <li>每日行程</li>
      </ul>
      <ul v-else-if="isSourcesMode" class="sidebar-list">
        <li>当前行程：{{ itinerary.destination }}</li>
        <li>来源记录：{{ sourceRecords.length }} 条</li>
        <li>来源仅作参考，不展示实时库存或可预订结果</li>
      </ul>
      <ul v-else class="sidebar-list">
        <li>当前行程：{{ itinerary.destination }}</li>
        <li>执行事件：{{ agentEvents.length }} 条</li>
        <li>只展示执行状态，不展示内部思维链</li>
      </ul>

      <div class="sidebar-actions">
        <button class="back-button" @click="$emit('backHome')">返回规划页</button>
        <button v-if="isResultMode" class="save-button" :disabled="saving" @click="handleSave">
          {{ saving ? "保存中..." : "保存行程" }}
        </button>
        <button class="history-button" @click="$emit('viewHistory')">历史列表</button>
        <button v-if="isResultMode" class="export-button" :disabled="exportingPdf" @click="openPdfExport">
          {{ exportingPdf ? "准备 PDF..." : "导出 PDF" }}
        </button>
        <button
          v-if="isResultMode"
          class="export-button export-button--light"
          :disabled="exportingMarkdown"
          @click="openMarkdownExport"
        >
          {{ exportingMarkdown ? "准备中..." : "导出 Markdown" }}
        </button>
      </div>
    </aside>

    <div class="result-grid">
      <template v-if="isResultMode">
      <section class="result-card">
        <div class="result-card__title">{{ itinerary.destination }}旅行计划</div>
        <div class="info-row"><strong>行程 ID：</strong>{{ itinerary.trip_id }}</div>
        <div class="info-row">
          <strong>日期：</strong>
          {{ itinerary.days[0]?.date || "待定" }} 至
          {{ itinerary.days[itinerary.days.length - 1]?.date || "待定" }}
        </div>
        <div class="info-row"><strong>地点：</strong>{{ itinerary.destination }}</div>
        <div class="info-row summary-text">{{ itinerary.summary }}</div>
        <div v-if="displayTips.length" class="overview-tips">
          <div class="overview-tips__title">旅行提示</div>
          <ul>
            <li v-for="tip in displayTips" :key="tip">{{ tip }}</li>
          </ul>
        </div>
      </section>

      <section class="result-card">
        <div class="result-card__title">预算明细</div>
        <div class="budget-grid">
          <div v-for="item in budgetItems" :key="item.label" class="budget-box">
            <div class="budget-box__label">{{ item.label }}</div>
            <div class="budget-box__value">{{ item.value }}</div>
            <div class="source-badge" :class="{ 'source-badge--caution': isNonRealtimeSource(item.sourceType) }">
              {{ sourceLabel(item.sourceType) }}
            </div>
          </div>
        </div>
        <div class="budget-total">
          <span>预估总费用</span>
          <strong>¥{{ itinerary.estimated_budget.toFixed(0) }}</strong>
        </div>
        <div class="budget-disclaimer">
          <span>以上价格为预估参考价，来源于本地演示、规则估算或外部检索，</span>
          <strong>非实时价格</strong>
          <span>，实际消费以现场为准。</span>
        </div>
      </section>

      <section v-if="candidateItineraries.length" class="result-card result-card--full">
        <div class="result-card__title">候选方案</div>
        <div class="candidate-grid">
          <article
            v-for="candidate in candidateItineraries"
            :key="candidate.candidate_id"
            class="candidate-card"
          >
            <div class="candidate-card__header">
              <strong>{{ candidate.title }}</strong>
              <span>¥{{ candidate.estimated_budget.toFixed(0) }}</span>
            </div>
            <p>{{ candidate.summary }}</p>
            <ul>
              <li v-for="diff in candidate.differences" :key="diff">{{ diff }}</li>
            </ul>
            <button type="button" class="candidate-card__button" @click="applyCandidate(candidate)">
              套用此方案
            </button>
          </article>
        </div>
      </section>

      <section class="result-card result-card--map">
        <div class="result-card__title">景点地图</div>
        <AmapTripMap :points="mapPoints" />
      </section>

      <section class="result-card result-card--weather">
        <div class="result-card__title">天气信息</div>

        <div v-if="weatherLoading" class="weather-state">正在加载天气信息...</div>
        <div v-else-if="weatherError" class="weather-state">{{ weatherError }}</div>
        <div v-else-if="weather" class="weather-grid">
          <article
            v-for="day in weather.days"
            :key="`${day.date}-${day.week}`"
            class="weather-card"
          >
            <div class="weather-card__date">
              {{ formatWeatherDate(day.date, day.week) }}
            </div>
            <div class="source-badge">{{ sourceLabel(day.source_type || weather.source_type) }}</div>
            <div class="weather-card__temp">
              {{ day.day_temp || "-" }}° / {{ day.night_temp || "-" }}°
            </div>
            <div class="weather-card__desc">白天：{{ day.day_weather || "未知" }}</div>
            <div class="weather-card__desc">夜间：{{ day.night_weather || "未知" }}</div>
          </article>
        </div>
        <div v-else class="weather-state">暂无天气信息。</div>
      </section>

      <section class="result-card result-card--browser">
        <div class="result-card__title">实时价格参考</div>
        <p class="browser-hint">
          点击下方按钮，系统会在 Edge 浏览器中打开携程对应页面并自动填入目的地和日期。
          价格请以页面实际显示为准，仅供出行参考。
        </p>
        <div class="browser-nav-buttons">
          <button
            class="browser-nav-btn browser-nav-btn--flight"
            :disabled="navigateLoading === 'flight'"
            @click="handleNavigate('flight')"
          >
            {{ navigateLoading === "flight" ? "打开中..." : "✈ 航班" }}
          </button>
          <button
            class="browser-nav-btn browser-nav-btn--train"
            :disabled="navigateLoading === 'train'"
            @click="handleNavigate('train')"
          >
            {{ navigateLoading === "train" ? "打开中..." : "🚄 高铁/火车" }}
          </button>
          <button
            class="browser-nav-btn browser-nav-btn--hotel"
            :disabled="navigateLoading === 'hotel'"
            @click="handleNavigate('hotel')"
          >
            {{ navigateLoading === "hotel" ? "打开中..." : "🏨 酒店" }}
          </button>
          <button
            class="browser-nav-btn browser-nav-btn--vacation"
            :disabled="navigateLoading === 'vacation'"
            @click="handleNavigate('vacation')"
          >
            {{ navigateLoading === "vacation" ? "打开中..." : "🎫 度假/门票" }}
          </button>
        </div>
        <div v-if="navigateError" class="browser-nav-error">{{ navigateError }}</div>
      </section>

      <section class="result-card result-card--full">
        <div class="result-card__title">智能调整行程</div>
        <div class="edit-panel">
          <div class="edit-panel__controls">
            <label class="edit-field">
              <span>调整范围</span>
              <select v-model="editScope">
                <option
                  v-for="day in itinerary.days"
                  :key="day.day_index"
                  :value="`day_${day.day_index}`"
                >
                  第{{ day.day_index }}天 · {{ day.theme || "未命名主题" }}
                </option>
              </select>
            </label>
            <button
              class="edit-submit-button"
              :disabled="editing"
              @click="handleEdit"
            >
              {{ editing ? "调整中..." : "智能调整" }}
            </button>
          </div>
          <textarea
            v-model="editInstruction"
            class="edit-textarea"
            rows="3"
            placeholder="例如：第二天轻松一点，不要安排太满；第三天想换成适合看日落的地点。"
          ></textarea>
        </div>
      </section>

      <section class="result-card result-card--full">
        <div class="result-card__title">按天花费</div>
        <div class="day-budget-grid">
          <article
            v-for="item in dayBudgetItems"
            :key="item.key"
            class="day-budget-card"
          >
            <div class="day-budget-card__header">
              <span>{{ item.title }}</span>
              <span>{{ item.subtitle }}</span>
            </div>
            <div class="day-budget-card__body">
              <div class="day-budget-row">
                <span>门票</span>
                <strong>¥{{ item.tickets.toFixed(0) }}</strong>
              </div>
              <div class="day-budget-row">
                <span>餐饮</span>
                <strong>¥{{ item.meals.toFixed(0) }}</strong>
              </div>
              <div class="day-budget-row">
                <span>交通</span>
                <strong>¥{{ item.transport.toFixed(0) }}</strong>
              </div>
              <div class="day-budget-row">
                <span>住宿</span>
                <strong>¥{{ item.hotel.toFixed(0) }}</strong>
              </div>
              <div class="day-budget-row day-budget-row--total">
                <span>当日合计</span>
                <strong>¥{{ item.total.toFixed(0) }}</strong>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="result-card result-card--full">
        <div class="result-card__title">地图点位明细</div>
        <div class="point-grid">
          <article v-for="point in mapPoints" :key="point.key" class="point-card">
            <div class="point-card__header">
              <span>第{{ point.dayIndex }}天 · {{ point.name }}</span>
              <span>{{ formatShortDate(point.date) }}</span>
            </div>

            <div class="point-card__body">
              <div
                v-if="point.imageUrl"
                class="point-card__image"
                :style="{ backgroundImage: `url(${point.imageUrl})` }"
              ></div>
              <div v-else class="point-card__image point-card__image--empty">
                暂无景点图片
              </div>
              <div class="point-card__line">
                <strong>主题：</strong>
                <span>{{ point.theme }}</span>
              </div>
              <div class="point-card__line">
                <strong>地址：</strong>
                <span>{{ point.address }}</span>
              </div>
              <div class="point-card__line">
                <strong>来源：</strong>
                <span class="source-badge" :class="{ 'source-badge--caution': isNonRealtimeSource(point.sourceType) }">
                  {{ sourceLabel(point.sourceType) }}
                </span>
              </div>
              <div class="point-card__desc">{{ point.description }}</div>
            </div>
          </article>
        </div>
      </section>

      <section class="result-card result-card--full">
        <div class="result-card__title">每日行程</div>
        <div class="day-list">
          <details
            v-for="day in itinerary.days"
            :key="day.day_index"
            :class="['day-card', { 'day-card--dragging': draggedDayIndex === day.day_index }]"
            :open="day.day_index === 1"
            draggable="true"
            @dragstart="handleDayDragStart(day.day_index)"
            @dragover.prevent
            @drop="handleDayDrop(day.day_index)"
          >
            <summary class="day-card__header">
              <span>第{{ day.day_index }}天 · {{ day.theme || "未命名主题" }}</span>
              <span class="day-card__meta">{{ formatShortDate(day.date) }}</span>
              <span class="drag-hint">拖拽排序</span>
            </summary>

            <div class="day-card__body">
              <div class="day-card__section">
                <strong>主要景点：</strong>
                <span>{{ day.spots[0]?.name || "未安排" }}</span>
                <span v-if="day.spots[0]" class="source-badge">{{ sourceLabel(day.spots[0].source_type) }}</span>
              </div>
              <div class="day-card__section">
                <strong>景点地址：</strong>
                <span>{{ day.spots[0]?.address || day.spots[0]?.location || "待补充" }}</span>
              </div>
              <div class="day-card__section">
                <strong>餐饮建议：</strong>
                <span>{{ day.meals[0]?.name || "未安排" }}</span>
                <span v-if="day.meals[0]" class="source-badge">{{ sourceLabel(day.meals[0].source_type) }}</span>
              </div>
              <div class="day-card__section">
                <strong>住宿安排：</strong>
                <span>{{ day.hotel?.name || "未安排" }}</span>
                <span v-if="day.hotel" class="source-badge">{{ sourceLabel(day.hotel.source_type) }}</span>
              </div>
              <div class="day-card__section">
                <strong>交通信息：</strong>
                <span>
                  {{
                    day.transport[0]?.distance_km != null
                      ? `${day.transport[0].distance_km.toFixed(2)} km / ${day.transport[0].estimated_minutes ?? 0} 分钟`
                      : day.transport[0]?.duration || "待补充"
                  }}
                </span>
                <span v-if="day.transport[0]" class="source-badge">{{ sourceLabel(day.transport[0].source_type) }}</span>
              </div>
              <div class="day-card__section">
                <strong>备注：</strong>
                <span>{{ day.notes[day.notes.length - 1] || "无" }}</span>
              </div>
            </div>
          </details>
        </div>
      </section>
      </template>

      <template v-else-if="isSourcesMode">
        <section class="result-card result-card--full">
          <div class="result-card__title">{{ itinerary.destination }}数据来源</div>
          <div class="mode-summary">
            当前页仅展示这条旅行结果使用到的来源记录，包括高德、天气、Tavily、本地演示和规则估算等来源。
          </div>
          <div v-if="sourceRecords.length" class="source-record-list">
            <article
              v-for="record in sourceRecords"
              :key="`${record.title}-${record.queried_at}`"
              class="source-record"
            >
              <div class="source-record__header">
                <strong>{{ record.title }}</strong>
                <span class="source-badge" :class="{ 'source-badge--caution': isNonRealtimeSource(record.source_type) }">
                  {{ sourceLabel(record.source_type) }}
                </span>
              </div>
              <p>{{ record.summary }}</p>
              <a v-if="record.url" :href="record.url" target="_blank" rel="noreferrer">查看来源</a>
            </article>
          </div>
          <div v-else class="empty-inline">当前行程暂时没有单独的来源记录。</div>
          <p class="source-disclaimer">
            本地演示数据、规则估算、Tavily 外部检索和 Browser 页面观察不代表实时库存、可预订结果或最终结算价格。
          </p>
        </section>
      </template>

      <template v-else-if="isAgentStatusMode">
        <section class="result-card result-card--full">
          <div class="result-card__title">{{ itinerary.destination }}Agent 执行状态</div>
          <div class="mode-summary">
            当前页只展示本次旅行规划相关的 Agent 和工具执行记录，不展示模型内部思维链。
          </div>
          <div v-if="agentEvents.length" class="agent-event-list">
            <article
              v-for="(event, index) in agentEvents"
              :key="`${event.request_id}-${event.agent}-${index}`"
              class="agent-event"
            >
              <div>
                <strong>{{ event.agent }}</strong>
                <span v-if="event.tool"> / {{ event.tool }}</span>
              </div>
              <div class="agent-event__meta">
                <span>{{ event.status }}</span>
                <span>{{ event.duration_ms }} ms</span>
                <span v-if="event.fallback">已降级</span>
                <span v-if="event.source_type">{{ sourceLabel(event.source_type) }}</span>
                <span v-if="event.error">{{ event.error }}</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-inline">当前行程暂时没有 Agent 执行记录。</div>
        </section>
      </template>
    </div>

    <AssistantPanel
      v-if="isResultMode"
      :itinerary="itinerary"
      @updated="handleAssistantUpdated"
    />
  </section>

  <section v-else class="empty-state">
    <div class="empty-state__card">
      <h2>还没有生成结果</h2>
      <p>先回到规划页生成一条 itinerary，结果页就会开始展示真实数据。</p>
      <button class="back-button" @click="$emit('backHome')">返回规划页</button>
    </div>
  </section>
</template>

<style scoped>
.result-page {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 22px;
}

.sidebar-card,
.result-card,
.empty-state__card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 22px 55px rgba(98, 116, 164, 0.12);
  backdrop-filter: blur(14px);
}

.sidebar-card {
  align-self: start;
  padding: 18px;
}

.sidebar-card__title,
.result-card__title {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, #6d82de 0%, #8a67cf 100%);
  color: #ffffff;
  font-size: 15px;
  font-weight: 700;
}

.sidebar-list {
  display: grid;
  gap: 12px;
  padding: 0;
  margin: 0 0 18px;
  list-style: none;
  color: #475467;
  font-size: 14px;
}

.sidebar-actions {
  display: grid;
  gap: 10px;
}

.back-button,
.save-button,
.history-button,
.export-button {
  width: 100%;
  border: none;
  border-radius: 14px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.back-button {
  background: rgba(109, 130, 222, 0.12);
  color: #5d66c3;
}

.save-button {
  background: linear-gradient(135deg, #7386e0 0%, #8f71d8 100%);
  color: #ffffff;
}

.save-button:disabled {
  opacity: 0.7;
  cursor: wait;
}

.export-button:disabled {
  opacity: 0.7;
  cursor: wait;
}

.history-button {
  background: rgba(79, 70, 229, 0.1);
  color: #5b5bd6;
}

.export-button {
  background: rgba(59, 130, 246, 0.12);
  color: #3568d4;
}

.export-button--light {
  background: rgba(16, 185, 129, 0.12);
  color: #0f8c63;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.result-card {
  padding: 18px;
}

.result-card--map,
.result-card--weather {
  min-height: 330px;
}

.result-card--full {
  grid-column: 1 / -1;
}

.info-row {
  margin-bottom: 10px;
  color: #475467;
  line-height: 1.7;
}

.summary-text {
  margin-top: 14px;
}

.overview-tips {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(109, 130, 222, 0.08), rgba(138, 103, 207, 0.08));
  border: 1px solid rgba(98, 116, 164, 0.08);
}

.overview-tips__title {
  margin-bottom: 8px;
  color: #465467;
  font-weight: 800;
}

.overview-tips ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
  color: #5d6675;
  line-height: 1.7;
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.budget-box {
  padding: 16px;
  border-radius: 16px;
  background: #f8faff;
  border: 1px solid rgba(98, 116, 164, 0.08);
}

.budget-box__label {
  color: #667085;
  font-size: 13px;
}

.budget-box__value {
  margin-top: 10px;
  color: #3b82f6;
  font-size: 22px;
  font-weight: 700;
}

.source-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  margin-top: 8px;
  border-radius: 999px;
  padding: 3px 9px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.source-badge--caution {
  background: rgba(245, 158, 11, 0.14);
  color: #92400e;
}

.budget-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #7386e0 0%, #8f71d8 100%);
  color: #ffffff;
}

.budget-total strong {
  font-size: 28px;
}

.budget-disclaimer {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.10);
  border: 1px solid rgba(245, 158, 11, 0.22);
  color: #92400e;
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
}

.candidate-grid,
.agent-event-list {
  display: grid;
  gap: 12px;
}

.candidate-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.candidate-card,
.agent-event {
  padding: 14px;
  border: 1px solid rgba(98, 116, 164, 0.08);
  border-radius: 16px;
  background: #fbfcff;
}

.candidate-card__header,
.agent-event {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.candidate-card__header {
  color: #42558d;
}

.candidate-card p {
  margin: 10px 0;
  color: #667085;
  line-height: 1.7;
}

.candidate-card ul {
  margin: 0 0 12px;
  padding-left: 18px;
  color: #475467;
  line-height: 1.7;
}

.candidate-card__button {
  border: none;
  border-radius: 12px;
  padding: 9px 12px;
  background: rgba(59, 130, 246, 0.12);
  color: #3568d4;
  font-weight: 800;
  cursor: pointer;
}

.agent-event__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  color: #667085;
  font-size: 12px;
}

.weather-state {
  color: #667085;
  line-height: 1.8;
}

.weather-grid {
  display: grid;
  gap: 12px;
}

.weather-card {
  padding: 14px;
  border-radius: 16px;
  background: #f8faff;
  border: 1px solid rgba(98, 116, 164, 0.08);
}

.weather-card__date {
  color: #465467;
  font-weight: 700;
}

.weather-card__temp {
  margin: 8px 0;
  color: #3b82f6;
  font-size: 24px;
  font-weight: 800;
}

.weather-card__desc {
  color: #667085;
  line-height: 1.7;
}

.edit-panel {
  display: grid;
  gap: 14px;
}

.edit-panel__controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 12px;
  align-items: end;
}

.edit-field {
  display: grid;
  gap: 8px;
  color: #465467;
  font-weight: 700;
}

.edit-field select,
.edit-textarea {
  width: 100%;
  border: 1px solid rgba(98, 116, 164, 0.18);
  border-radius: 14px;
  background: #fbfcff;
  color: #334155;
  font: inherit;
  outline: none;
}

.edit-field select {
  min-height: 44px;
  padding: 0 14px;
}

.edit-textarea {
  resize: vertical;
  min-height: 92px;
  padding: 12px 14px;
  line-height: 1.7;
}

.edit-field select:focus,
.edit-textarea:focus {
  border-color: rgba(109, 130, 222, 0.65);
  box-shadow: 0 0 0 3px rgba(109, 130, 222, 0.12);
}

.edit-submit-button {
  min-height: 44px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #7386e0 0%, #8f71d8 100%);
  color: #ffffff;
  font-weight: 800;
  cursor: pointer;
}

.edit-submit-button:disabled {
  opacity: 0.7;
  cursor: wait;
}

.day-budget-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.day-budget-card {
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(98, 116, 164, 0.08);
  background: #fbfcff;
}

.day-budget-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(109, 130, 222, 0.08);
  color: #465467;
  font-weight: 700;
}

.day-budget-card__body {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.day-budget-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #475467;
}

.day-budget-row--total {
  padding-top: 10px;
  border-top: 1px solid rgba(98, 116, 164, 0.08);
  color: #2f4fa5;
}

.point-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.point-card {
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(98, 116, 164, 0.08);
  background: #fbfcff;
}

.point-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(109, 130, 222, 0.08);
  color: #465467;
  font-weight: 700;
}

.point-card__body {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.point-card__image {
  min-height: 150px;
  border-radius: 14px;
  background-position: center;
  background-size: cover;
  background-color: #eef3ff;
}

.point-card__image--empty {
  display: grid;
  place-items: center;
  color: #7b8494;
  font-weight: 700;
  background:
    linear-gradient(135deg, rgba(129, 179, 255, 0.18), rgba(137, 108, 230, 0.15)),
    #f7f9ff;
}

.point-card__line {
  color: #475467;
  line-height: 1.7;
}

.point-card__desc {
  padding-top: 10px;
  border-top: 1px solid rgba(98, 116, 164, 0.08);
  color: #667085;
  line-height: 1.7;
}

.source-record-list {
  display: grid;
  gap: 12px;
}

.mode-summary,
.empty-inline {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8faff;
  border: 1px solid rgba(98, 116, 164, 0.08);
  color: #5d6675;
  line-height: 1.7;
}

.empty-inline {
  color: #7b8494;
  font-weight: 700;
}

.source-record {
  padding: 14px;
  border: 1px solid rgba(98, 116, 164, 0.08);
  border-radius: 16px;
  background: #fbfcff;
}

.source-record__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #465467;
}

.source-record p,
.source-disclaimer {
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.7;
}

.source-record a {
  display: inline-block;
  margin-top: 8px;
  color: #3b82f6;
  font-weight: 700;
}

.day-list {
  display: grid;
  gap: 12px;
}

.day-card {
  border-radius: 18px;
  border: 1px solid rgba(98, 116, 164, 0.08);
  background: #fbfcff;
  overflow: hidden;
}

.day-card--dragging {
  opacity: 0.55;
}

.day-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(109, 130, 222, 0.08);
  color: #465467;
  font-weight: 700;
  cursor: pointer;
  list-style: none;
}

.day-card__header::-webkit-details-marker {
  display: none;
}

.day-card__header::after {
  content: "展开";
  flex: 0 0 auto;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(109, 130, 222, 0.12);
  color: #5b5bd6;
  font-size: 12px;
}

.day-card[open] .day-card__header::after {
  content: "收起";
}

.day-card__meta {
  margin-left: auto;
  color: #667085;
  font-size: 13px;
}

.drag-hint {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 4px 10px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-size: 12px;
  font-weight: 800;
}

.day-card__body {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.day-card__section {
  color: #475467;
  line-height: 1.7;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 360px;
}

.empty-state__card {
  max-width: 560px;
  padding: 36px;
  text-align: center;
}

.empty-state__card h2 {
  margin: 0 0 12px;
}

.empty-state__card p {
  margin: 0 0 18px;
  color: #667085;
  line-height: 1.7;
}

.result-card--browser {
  grid-column: 1 / -1;
}

.browser-hint {
  margin: 0 0 16px;
  padding: 11px 14px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.06);
  border: 1px solid rgba(59, 130, 246, 0.12);
  color: #3b5f8a;
  font-size: 13px;
  line-height: 1.7;
}

.browser-nav-buttons {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.browser-nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 52px;
  border: none;
  border-radius: 14px;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s;
}

.browser-nav-btn--flight {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
}

.browser-nav-btn--train {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #ffffff;
}

.browser-nav-btn--hotel {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #ffffff;
}

.browser-nav-btn--vacation {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: #1a3a2a;
}

.browser-nav-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.browser-nav-btn:not(:disabled):hover {
  opacity: 0.9;
}

.browser-nav-error {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(245, 87, 108, 0.08);
  color: #c0392b;
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 960px) {
  .result-page {
    grid-template-columns: 1fr;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }

  .edit-panel__controls {
    grid-template-columns: 1fr;
  }

  .browser-nav-buttons {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
