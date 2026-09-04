import { defineStore } from "pinia";
import { computed, ref } from "vue";

import {
  api,
  type FetchResult,
  type NewsItem,
  type RuntimeSettings,
  type Source,
  type Stats,
  type TelegramUserStatus,
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
  const telegramUser = ref<TelegramUserStatus | null>(null);
  const telegramApiId = ref("");
  const telegramApiHash = ref("");
  const telegramPhone = ref("");
  const telegramCode = ref("");
  const telegramPassword = ref("");
  const telegramCodeSent = ref(false);

  const isDemo = computed(() => settings.value?.app_mode === "demo");
  const uniqueShare = computed(() => {
    const published = stats.value?.published ?? 0;
    const duplicates = stats.value?.duplicates ?? 0;
    const newsTotal = published + duplicates;
    if (!newsTotal) {
      return 0;
    }
    return Math.round((published / newsTotal) * 100);
  });

  async function refresh() {
    isLoading.value = true;
    hasError.value = "";
    try {
      const [nextStats, nextSources, nextItems, nextSettings, nextTelegram] = await Promise.all([
        api.stats(),
        api.sources(),
        api.items(statusFilter.value || undefined),
        api.settings(),
        api.telegramUser(),
      ]);
      stats.value = nextStats;
      sources.value = nextSources;
      items.value = nextItems;
      settings.value = nextSettings;
      telegramUser.value = nextTelegram;
      telegramCodeSent.value = nextTelegram.code_sent;
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

  async function saveTelegramCredentials() {
    const apiId = Number(telegramApiId.value);
    if (!apiId || !telegramApiHash.value.trim()) {
      hasError.value = "Укажите API ID и API Hash с my.telegram.org";
      return;
    }
    isBusy.value = true;
    hasError.value = "";
    try {
      telegramUser.value = await api.saveTelegramCredentials(apiId, telegramApiHash.value.trim());
      telegramApiHash.value = "";
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось сохранить API-данные";
    } finally {
      isBusy.value = false;
    }
  }

  async function sendTelegramCode() {
    if (!telegramPhone.value.trim()) {
      hasError.value = "Укажите номер телефона в формате +79001234567";
      return;
    }
    isBusy.value = true;
    hasError.value = "";
    try {
      const apiId = Number(telegramApiId.value);
      const apiHash = telegramApiHash.value.trim();
      await api.sendTelegramCode(
        telegramPhone.value.trim(),
        apiId || undefined,
        apiHash || undefined,
      );
      telegramCodeSent.value = true;
      telegramUser.value = await api.telegramUser();
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось отправить код";
    } finally {
      isBusy.value = false;
    }
  }

  async function signInTelegram() {
    if (!telegramPhone.value.trim() || !telegramCode.value.trim()) {
      hasError.value = "Введите номер и код из Telegram";
      return;
    }
    isBusy.value = true;
    hasError.value = "";
    try {
      telegramUser.value = await api.signInTelegram(
        telegramPhone.value.trim(),
        telegramCode.value.trim(),
        telegramPassword.value.trim() || undefined,
      );
      telegramCode.value = "";
      telegramPassword.value = "";
      telegramCodeSent.value = false;
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось войти в Telegram";
    } finally {
      isBusy.value = false;
    }
  }

  async function logoutTelegram() {
    isBusy.value = true;
    hasError.value = "";
    try {
      telegramUser.value = await api.logoutTelegram();
      telegramCodeSent.value = false;
      telegramCode.value = "";
      telegramPassword.value = "";
    } catch (error) {
      hasError.value = error instanceof Error ? error.message : "Не удалось выйти из Telegram";
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
    telegramUser,
    telegramApiId,
    telegramApiHash,
    telegramPhone,
    telegramCode,
    telegramPassword,
    telegramCodeSent,
    isDemo,
    uniqueShare,
    refresh,
    addSource,
    toggleSource,
    removeSource,
    saveSettings,
    fetchNow,
    resetDemo,
    saveTelegramCredentials,
    sendTelegramCode,
    signInTelegram,
    logoutTelegram,
  };
});
