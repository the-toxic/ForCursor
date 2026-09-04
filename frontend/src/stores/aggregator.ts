import { defineStore } from "pinia";
import { computed, ref } from "vue";

import {
  api,
  type FetchResult,
  type NewsItem,
  type RuntimeSettings,
  type Source,
  type Stats,
} from "../api/client";

export const useAggregatorStore = defineStore("aggregator", () => {
  const stats = ref<Stats | null>(null);
  const sources = ref<Source[]>([]);
  const items = ref<NewsItem[]>([]);
  const settings = ref<RuntimeSettings | null>(null);
  const isLoading = ref(false);
  const isBusy = ref(false);
  const hasError = ref("");
  const lastResult = ref<FetchResult | null>(null);
  const statusFilter = ref("");
  const newUsername = ref("");

  const isDemo = computed(() => settings.value?.app_mode === "demo");
  const uniqueShare = computed(() => {
    const total = stats.value?.items_total ?? 0;
    if (!total) {
      return 0;
    }
    return Math.round(((stats.value?.published ?? 0) / total) * 100);
  });

  async function refresh() {
    isLoading.value = true;
    hasError.value = "";
    try {
      const [nextStats, nextSources, nextItems, nextSettings] = await Promise.all([
        api.stats(),
        api.sources(),
        api.items(statusFilter.value || undefined),
        api.settings(),
      ]);
      stats.value = nextStats;
      sources.value = nextSources;
      items.value = nextItems;
      settings.value = nextSettings;
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось загрузить данные";
    } finally {
      isLoading.value = false;
    }
  }

  async function addSource() {
    if (!newUsername.value.trim()) {
      return;
    }
    isBusy.value = true;
    hasError.value = "";
    try {
      await api.addSource(newUsername.value.trim());
      newUsername.value = "";
      await refresh();
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось добавить канал";
    } finally {
      isBusy.value = false;
    }
  }

  async function toggleSource(source: Source) {
    await api.toggleSource(source.id, !source.enabled);
    await refresh();
  }

  async function removeSource(source: Source) {
    await api.deleteSource(source.id);
    await refresh();
  }

  async function saveSettings() {
    if (!settings.value) {
      return;
    }
    isBusy.value = true;
    try {
      settings.value = await api.saveSettings({
        similarity_threshold: settings.value.similarity_threshold,
        poll_interval_seconds: settings.value.poll_interval_seconds,
        min_text_length: settings.value.min_text_length,
        target_channel: settings.value.target_channel,
      });
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось сохранить настройки";
    } finally {
      isBusy.value = false;
    }
  }

  async function fetchNow() {
    isBusy.value = true;
    hasError.value = "";
    try {
      lastResult.value = await api.fetchNow();
      await refresh();
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Сбор не удался";
    } finally {
      isBusy.value = false;
    }
  }

  async function resetDemo() {
    isBusy.value = true;
    hasError.value = "";
    try {
      lastResult.value = await api.resetDemo();
      await refresh();
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Сброс не удался";
    } finally {
      isBusy.value = false;
    }
  }

  return {
    stats,
    sources,
    items,
    settings,
    isLoading,
    isBusy,
    hasError,
    lastResult,
    statusFilter,
    newUsername,
    isDemo,
    uniqueShare,
    refresh,
    addSource,
    toggleSource,
    removeSource,
    saveSettings,
    fetchNow,
    resetDemo,
  };
});
