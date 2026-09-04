<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";

import { ACCESS_KEY, clearSession, hasAccess, saveSession } from "./auth";
import { useAggregatorStore } from "./stores/aggregator";

const store = useAggregatorStore();
const isAuthed = ref(false);
const accessKey = ref("");
const loginError = ref("");

function lockScreen() {
  isAuthed.value = false;
  accessKey.value = "";
}

function enterSite() {
  loginError.value = "";
  if (accessKey.value.trim() !== ACCESS_KEY) {
    loginError.value = "Неверный ключ";
    return;
  }
  saveSession(ACCESS_KEY);
  isAuthed.value = true;
  void store.refresh();
}

function logout() {
  clearSession();
  lockScreen();
}

onMounted(() => {
  window.addEventListener("uniq-news-unauthorized", lockScreen);
  if (hasAccess()) {
    isAuthed.value = true;
    void store.refresh();
  }
});

onUnmounted(() => {
  window.removeEventListener("uniq-news-unauthorized", lockScreen);
});

watch(
  () => store.statusFilter,
  () => {
    if (isAuthed.value) {
      void store.refresh();
    }
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

function sourceLabel(name: string): string {
  if (name.startsWith("invite_") || name.startsWith("+") || name.includes(" ")) {
    return name;
  }
  return `@${name}`;
}
</script>

<template>
  <div
    v-if="!isAuthed"
    class="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4"
  >
    <form
      class="rounded-3xl border border-white/10 bg-slate-950/50 p-6 sm:p-8"
      @submit.prevent="enterSite"
    >
      <p class="text-sm font-medium uppercase tracking-[0.2em] text-amber-300/80">Telegram · дедуп</p>
      <h1 class="mt-3 text-2xl font-semibold text-white">Вход</h1>
      <p class="mt-2 text-sm text-slate-400">Введите ключ, чтобы открыть агрегатор.</p>
      <input
        v-model="accessKey"
        type="password"
        autocomplete="current-password"
        placeholder="Ключ доступа"
        class="mt-5 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-amber-400/60"
      />
      <p v-if="loginError" class="mt-2 text-sm text-rose-300">{{ loginError }}</p>
      <button
        type="submit"
        class="mt-5 w-full rounded-xl bg-amber-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-amber-300"
      >
        Войти
      </button>
    </form>
  </div>

  <div v-else class="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <header class="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p class="text-sm font-medium uppercase tracking-[0.2em] text-amber-300/80">Telegram · дедуп</p>
        <h1 class="mt-2 text-3xl font-semibold text-white sm:text-4xl">
          Агрегатор уникальных новостей
        </h1>
        <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
          Бот читает выбранные каналы, отбрасывает повторы по смыслу и тексту,
          а в ваш канал отправляет только то, чего ещё не было. Закрытые каналы
          подключаются по invite-ссылке после входа в Telegram-аккаунт.
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
        <button
          type="button"
          class="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10"
          @click="logout"
        >
          Выйти
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
              <span class="text-xs text-slate-400">{{ sourceLabel(item.source_username) }}</span>
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
          <p class="mt-1 text-sm text-slate-400">
            Публичный @username или ссылка-приглашение
            <span class="text-slate-300">t.me/+…</span> / <span class="text-slate-300">t.me/joinchat/…</span>.
          </p>

          <form class="mt-4 flex gap-2" @submit.prevent="store.addSource">
            <input
              v-model="store.newUsername"
              type="text"
              placeholder="@channel или https://t.me/+invite"
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
                <p class="text-sm font-medium text-white">{{ source.title || sourceLabel(source.username) }}</p>
                <p class="text-xs text-slate-400">
                  <span
                    v-if="source.source_kind === 'private'"
                    class="mr-1 rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-medium text-violet-200 ring-1 ring-violet-400/20"
                  >
                    закрытый
                  </span>
                  <span v-if="source.source_kind === 'private'">по ссылке-приглашению</span>
                  <span v-else>{{ sourceLabel(source.username) }}</span>
                </p>
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
          <h2 class="text-lg font-semibold text-white">Закрытые каналы</h2>
          <p class="mt-1 text-sm text-slate-400">
            Бот не умеет входить по invite-ссылке. Нужен ваш Telegram-аккаунт:
            API ID и Hash с
            <a
              class="text-amber-200 underline decoration-amber-200/40 underline-offset-2"
              href="https://my.telegram.org/apps"
              target="_blank"
              rel="noreferrer"
            >my.telegram.org</a>,
            затем телефон и код.
          </p>

          <div v-if="store.telegramUser?.authorized" class="mt-4 rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-3">
            <p class="text-sm text-emerald-100">
              Вошли как
              {{ store.telegramUser.first_name || "аккаунт" }}
              <span v-if="store.telegramUser.username">@{{ store.telegramUser.username }}</span>
              <span v-if="store.telegramUser.phone" class="text-emerald-200/80"> · +{{ store.telegramUser.phone }}</span>
            </p>
            <button
              type="button"
              class="mt-3 rounded-lg px-2 py-1 text-xs text-emerald-100 hover:bg-white/10"
              :disabled="store.isBusy"
              @click="store.logoutTelegram"
            >
              Выйти из Telegram
            </button>
          </div>

          <div v-else class="mt-4 space-y-3">
            <p
              v-if="store.telegramUser?.configured"
              class="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"
            >
              API-данные сохранены. Осталось войти по номеру телефона.
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="block text-sm text-slate-300">
                API ID
                <input
                  v-model="store.telegramApiId"
                  type="text"
                  inputmode="numeric"
                  class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  placeholder="123456"
                />
              </label>
              <label class="block text-sm text-slate-300">
                API Hash
                <input
                  v-model="store.telegramApiHash"
                  type="password"
                  class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  placeholder="из my.telegram.org"
                />
              </label>
            </div>
            <button
              type="button"
              class="w-full rounded-xl border border-white/10 bg-white/5 py-2 text-sm font-medium text-white hover:bg-white/10 disabled:opacity-50"
              :disabled="store.isBusy"
              @click="store.saveTelegramCredentials"
            >
              Сохранить API ID и Hash
            </button>
            <label class="block text-sm text-slate-300">
              Телефон
              <input
                v-model="store.telegramPhone"
                type="tel"
                class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                placeholder="+79001234567"
              />
            </label>
            <button
              type="button"
              class="w-full rounded-xl bg-white px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              :disabled="store.isBusy"
              @click="store.sendTelegramCode"
            >
              Получить код
            </button>
            <div v-if="store.telegramCodeSent" class="space-y-3">
              <label class="block text-sm text-slate-300">
                Код из Telegram
                <input
                  v-model="store.telegramCode"
                  type="text"
                  class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  placeholder="12345"
                />
              </label>
              <label class="block text-sm text-slate-300">
                Пароль 2FA, если включён
                <input
                  v-model="store.telegramPassword"
                  type="password"
                  class="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  placeholder="необязательно"
                />
              </label>
              <button
                type="button"
                class="w-full rounded-xl bg-amber-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
                :disabled="store.isBusy"
                @click="store.signInTelegram"
              >
                Войти в Telegram
              </button>
            </div>
          </div>
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
