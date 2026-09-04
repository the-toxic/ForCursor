<script setup lang="ts">
import { onMounted, watch } from "vue";

import { useAggregatorStore } from "./stores/aggregator";

const store = useAggregatorStore();

onMounted(() => {
  void store.refresh();
});

watch(
  () => store.statusFilter,
  () => {
    void store.refresh();
  },
);

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "ещё не запускали";
  }
  return new Date(value).toLocaleString("ru-RU");
}

function statusLabel(status: string): string {
  if (status === "published") {
    return "уникальная";
  }
  if (status === "duplicate") {
    return "повтор";
  }
  return "пропуск";
}

function statusClass(status: string): string {
  if (status === "published") {
    return "bg-emerald-500/15 text-emerald-300 ring-emerald-400/20";
  }
  if (status === "duplicate") {
    return "bg-amber-500/15 text-amber-300 ring-amber-400/20";
  }
  return "bg-slate-500/15 text-slate-300 ring-slate-400/20";
}
</script>

<template>
  <div class="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <header class="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p class="text-sm font-medium uppercase tracking-[0.2em] text-amber-300/80">Telegram · дедуп</p>
        <h1 class="mt-2 text-3xl font-semibold text-white sm:text-4xl">
          Агрегатор уникальных новостей
        </h1>
        <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
          Бот читает выбранные каналы, отбрасывает повторы по смыслу и тексту,
          а в ваш канал отправляет только то, чего ещё не было.
        </p>
      </div>
      <div class="flex flex-wrap gap-3">
        <button
          type="button"
          class="rounded-xl bg-amber-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-amber-300 disabled:opacity-50"
          :disabled="store.isBusy"
          @click="store.fetchNow"
        >
          Собрать сейчас
        </button>
        <button
          v-if="store.isDemo"
          type="button"
          class="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10 disabled:opacity-50"
          :disabled="store.isBusy"
          @click="store.resetDemo"
        >
          Пересобрать демо
        </button>
      </div>
    </header>

    <div
      v-if="store.isDemo"
      class="mb-6 rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100"
    >
      Сейчас включён demo-режим: живой Telegram не нужен. На демо-ленте специально есть
      одинаковые новости из разных каналов, чтобы было видно, как срабатывает дедуп.
    </div>

    <p v-if="store.hasError" class="mb-6 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
      {{ store.hasError }}
    </p>

    <section class="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article class="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p class="text-sm text-slate-400">Уникальных</p>
        <p class="mt-2 text-3xl font-semibold text-white">{{ store.stats?.published ?? 0 }}</p>
      </article>
      <article class="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p class="text-sm text-slate-400">Повторов отсеяно</p>
        <p class="mt-2 text-3xl font-semibold text-white">{{ store.stats?.duplicates ?? 0 }}</p>
      </article>
      <article class="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p class="text-sm text-slate-400">Источников</p>
        <p class="mt-2 text-3xl font-semibold text-white">{{ store.stats?.sources ?? 0 }}</p>
      </article>
      <article class="rounded-2xl border border-white/10 bg-white/5 p-5">
        <p class="text-sm text-slate-400">Доля уникальных</p>
        <p class="mt-2 text-3xl font-semibold text-white">{{ store.uniqueShare }}%</p>
      </article>
    </section>

    <div class="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <section class="rounded-3xl border border-white/10 bg-slate-950/40 p-5 sm:p-6">
        <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 class="text-lg font-semibold text-white">Лента после дедупа</h2>
            <p class="text-sm text-slate-400">Последний сбор: {{ formatDate(store.stats?.last_fetch_at) }}</p>
          </div>
          <select
            v-model="store.statusFilter"
            class="rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-100"
          >
            <option value="">Все статусы</option>
            <option value="published">Только уникальные</option>
            <option value="duplicate">Только повторы</option>
            <option value="skipped">Только пропуски</option>
          </select>
        </div>

        <div v-if="store.isLoading" class="py-16 text-center text-sm text-slate-400">Загружаем ленту…</div>
        <div v-else-if="!store.items.length" class="py-16 text-center text-sm text-slate-400">
          Пока пусто. Нажмите «Собрать сейчас».
        </div>
        <ul v-else class="space-y-4">
          <li
            v-for="item in store.items"
            :key="item.id"
            class="rounded-2xl border border-white/8 bg-white/4 p-4"
          >
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <span class="rounded-full px-2.5 py-1 text-xs font-medium ring-1" :class="statusClass(item.status)">
                {{ statusLabel(item.status) }}
              </span>
              <span class="text-xs text-slate-400">@{{ item.source_username }}</span>
              <span v-if="item.similarity" class="text-xs text-slate-500">
                похожесть {{ Math.round(item.similarity * 100) }}%
              </span>
            </div>
            <p class="whitespace-pre-wrap text-sm leading-6 text-slate-100">
              {{ item.raw_text || "Без текста" }}
            </p>
          </li>
        </ul>
      </section>

      <div class="space-y-6">
        <section class="rounded-3xl border border-white/10 bg-slate-950/40 p-5 sm:p-6">
          <h2 class="text-lg font-semibold text-white">Каналы-источники</h2>
          <p class="mt-1 text-sm text-slate-400">Публичные каналы, которые бот будет сравнивать между собой.</p>

          <form class="mt-4 flex gap-2" @submit.prevent="store.addSource">
            <input
              v-model="store.newUsername"
              type="text"
              placeholder="@channel или username"
              class="w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none ring-amber-400/0 focus:ring-2"
            />
            <button
              type="submit"
              class="rounded-xl bg-white px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              :disabled="store.isBusy"
            >
              Добавить
            </button>
          </form>

          <ul class="mt-4 space-y-3">
            <li
              v-for="source in store.sources"
              :key="source.id"
              class="flex items-center justify-between gap-3 rounded-2xl border border-white/8 bg-white/4 px-3 py-3"
            >
              <div>
                <p class="text-sm font-medium text-white">{{ source.title || source.username }}</p>
                <p class="text-xs text-slate-400">@{{ source.username }}</p>
                <p v-if="source.error" class="mt-1 text-xs text-rose-300">{{ source.error }}</p>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="rounded-lg px-2 py-1 text-xs text-slate-300 hover:bg-white/10"
                  @click="store.toggleSource(source)"
                >
                  {{ source.enabled ? "выкл" : "вкл" }}
                </button>
                <button
                  type="button"
                  class="rounded-lg px-2 py-1 text-xs text-rose-200 hover:bg-rose-500/10"
                  @click="store.removeSource(source)"
                >
                  удалить
                </button>
              </div>
            </li>
          </ul>
        </section>

        <section class="rounded-3xl border border-white/10 bg-slate-950/40 p-5 sm:p-6">
          <h2 class="text-lg font-semibold text-white">Настройки бота</h2>
          <div v-if="store.settings" class="mt-4 space-y-4">
            <label class="block text-sm text-slate-300">
              Канал назначения
              <input
                v-model="store.settings.target_channel"
                class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                placeholder="@my_unique_news"
              />
            </label>
            <label class="block text-sm text-slate-300">
              Порог похожести: {{ Math.round(store.settings.similarity_threshold * 100) }}%
              <input
                v-model.number="store.settings.similarity_threshold"
                type="range"
                min="0.6"
                max="0.95"
                step="0.01"
                class="mt-2 w-full"
              />
            </label>
            <label class="block text-sm text-slate-300">
              Интервал опроса, сек
              <input
                v-model.number="store.settings.poll_interval_seconds"
                type="number"
                min="15"
                class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
              />
            </label>
            <label class="block text-sm text-slate-300">
              Минимальная длина текста
              <input
                v-model.number="store.settings.min_text_length"
                type="number"
                min="10"
                class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
              />
            </label>
            <button
              type="button"
              class="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 text-sm font-medium text-white hover:bg-white/10 disabled:opacity-50"
              :disabled="store.isBusy"
              @click="store.saveSettings"
            >
              Сохранить настройки
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
