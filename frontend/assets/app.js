(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor("#1a1510");
      tg.setBackgroundColor("#1a1510");
    } catch (_) {}
  }

  const els = {
    title: document.getElementById("title"),
    meta: document.getElementById("meta"),
    pageHeader: document.getElementById("page-header"),
    sections: document.getElementById("sections"),
    error: document.getElementById("error"),
    empty: document.getElementById("empty"),
    bar: document.getElementById("progress-bar"),
    fill: document.getElementById("progress-fill"),
    label: document.getElementById("progress-label"),
    congrats: document.getElementById("congrats"),
    tabs: document.getElementById("tabs"),
    viewWorkout: document.getElementById("view-workout"),
    viewSuccess: document.getElementById("view-success"),
    viewAdmin: document.getElementById("view-admin"),
    successLabel: document.getElementById("success-label"),
    successSummary: document.getElementById("success-summary"),
    successCal: document.getElementById("success-cal"),
    successPrev: document.getElementById("success-prev"),
    successNext: document.getElementById("success-next"),
    successKindList: document.getElementById("success-kind-list"),
    successMonthWrap: document.getElementById("success-month-wrap"),
    successDayWrap: document.getElementById("success-day-wrap"),
    successDayBack: document.getElementById("success-day-back"),
    successDayTitle: document.getElementById("success-day-title"),
    successDayStatus: document.getElementById("success-day-status"),
    successDayBase: document.getElementById("success-day-base"),
    successDayBonus: document.getElementById("success-day-bonus"),
    successDayLogs: document.getElementById("success-day-logs"),
    successDayPrev: document.getElementById("success-day-prev"),
    successDayNext: document.getElementById("success-day-next"),
    successDayComplete: document.getElementById("success-day-complete"),
    btnCompleteBase: document.getElementById("btn-complete-base"),
    logForm: document.getElementById("success-log-form"),
    logKind: document.getElementById("log-kind"),
    logComment: document.getElementById("log-comment"),
    adminCategory: document.getElementById("admin-category"),
    adminList: document.getElementById("admin-list"),
    adminForm: document.getElementById("admin-form"),
    formTitle: document.getElementById("form-title"),
    fCategory: document.getElementById("f-category"),
    fName: document.getElementById("f-name"),
    fDesc: document.getElementById("f-desc"),
    fVideo: document.getElementById("f-video"),
    fOrder: document.getElementById("f-order"),
    fActive: document.getElementById("f-active"),
  };

  const blockBySection = {
    slot1: "base",
    slot2: "base",
    slot3: "base",
    posture_base: "base",
    neck: "base",
    muscle: "base",
    more_posture: "bonus",
    more_glutes: "bonus",
  };

  const expandedExtras = {
    more_posture: false,
    more_glutes: false,
  };

  let categories = [];
  let editingId = null;
  let isAdmin = false;
  let currentPlan = null;
  let successCursor = null; // { year, month }
  let selectedSuccessDate = null;
  let monthLogsCache = [];
  let activeLogKind = null;

  const CONGRATS_TEXT =
    "Базовый круг закрыт — отличная работа! Можно добавить ещё осанку или попу.";

  function showBaseCongratsPopup() {
    if (tg?.HapticFeedback) {
      try { tg.HapticFeedback.notificationOccurred("success"); } catch (_) {}
    }
    if (typeof tg?.showPopup === "function") {
      tg.showPopup({
        title: "Поздравляем!",
        message: CONGRATS_TEXT,
        buttons: [{ type: "ok" }],
      });
    } else if (typeof tg?.showAlert === "function") {
      tg.showAlert(CONGRATS_TEXT);
    }
  }

  function ensureCongratsEl() {
    if (els.congrats) return els.congrats;
    const bar = els.bar;
    const node = document.createElement("p");
    node.id = "congrats";
    node.className = "congrats";
    node.hidden = true;
    if (bar && bar.parentNode) {
      bar.insertAdjacentElement("afterend", node);
    } else {
      document.getElementById("view-workout")?.prepend(node);
    }
    els.congrats = node;
    return node;
  }

  function setCongratsVisible(visible, text = "") {
    const el = ensureCongratsEl();
    el.hidden = !visible;
    el.textContent = visible ? text : "";
  }

  function applyPlan(plan) {
    const justFinished = !!(currentPlan && !currentPlan.base_done && plan.base_done);
    currentPlan = plan;
    renderWorkout(plan);
    if (justFinished) showBaseCongratsPopup();
  }

  function initData() {
    return tg?.initData || "";
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
      ...(options.headers || {}),
    };
    const res = await fetch(path, { ...options, headers });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (_) {}
    if (!res.ok) {
      const detail = data?.detail || res.statusText || "Ошибка запроса";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function showError(msg) {
    els.error.hidden = false;
    els.error.textContent = msg;
  }

  function clearError() {
    els.error.hidden = true;
  }

  function openVideo(url) {
    const go = () => {
      if (tg?.openTelegramLink && /^(https?:\/\/)?(t\.me|telegram\.me)\//i.test(url)) {
        tg.openTelegramLink(url.startsWith("http") ? url : `https://${url}`);
      } else if (tg?.openLink) {
        tg.openLink(url);
      } else {
        window.open(url, "_blank");
      }
    };

    api("/api/channel/status")
      .then((st) => {
        if (st.required && !st.subscribed) {
          const invite = st.invite_link;
          const msg = invite
            ? "Сначала вступи в канал с видео — без подписки ролики не откроются."
            : "Нужна подписка на канал с видео. Напиши боту /start.";
          if (typeof tg?.showPopup === "function" && invite) {
            tg.showPopup({
              title: "Нужна подписка",
              message: msg,
              buttons: [
                { id: "join", type: "default", text: "Вступить" },
                { type: "cancel" },
              ],
            }, (btnId) => {
              if (btnId === "join") {
                if (tg.openTelegramLink) tg.openTelegramLink(invite);
                else if (tg.openLink) tg.openLink(invite);
              }
            });
          } else if (typeof tg?.showAlert === "function") {
            tg.showAlert(msg, () => {
              if (invite) {
                if (tg.openTelegramLink) tg.openTelegramLink(invite);
                else if (tg.openLink) tg.openLink(invite);
              }
            });
          } else {
            alert(msg);
            if (invite) window.open(invite, "_blank");
          }
          return;
        }
        go();
      })
      .catch(() => go());
  }

  function setView(name) {
    els.viewWorkout.hidden = name !== "workout";
    if (els.viewSuccess) els.viewSuccess.hidden = name !== "success";
    els.viewAdmin.hidden = name !== "admin";
    els.adminForm.hidden = true;
    document.getElementById("admin-list-wrap")?.classList.remove("is-hidden");
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === name);
    });
    if (name === "admin") {
      if (els.pageHeader) els.pageHeader.classList.remove("is-hidden");
      els.title.classList.remove("date-heading");
      els.title.textContent = "Админка";
      els.meta.hidden = false;
      els.meta.textContent = "Каталог упражнений в базе";
      els.bar.hidden = true;
      if (els.congrats) els.congrats.hidden = true;
      loadAdminList();
    } else if (name === "success") {
      if (els.pageHeader) els.pageHeader.classList.add("is-hidden");
      els.bar.hidden = true;
      if (els.congrats) els.congrats.hidden = true;
      showSuccessMonth();
      loadSuccessMonth().catch((err) => showError(err.message));
    } else if (name === "workout") {
      if (els.pageHeader) els.pageHeader.classList.remove("is-hidden");
      if (currentPlan) renderWorkout(currentPlan);
    }
  }

  function showSuccessMonth() {
    selectedSuccessDate = null;
    if (els.successMonthWrap) els.successMonthWrap.hidden = false;
    if (els.successDayWrap) els.successDayWrap.hidden = true;
  }

  const LOG_EMOJI = {
    strength: "💪",
    face: "😊",
    note: "📝",
  };

  const LOG_KIND_LABEL = {
    strength: "Силовые",
    face: "Фейсфитнес",
    note: "Заметки",
  };

  function updateLogKindCounts() {
    const daysByKind = { strength: new Set(), face: new Set(), note: new Set() };
    for (const log of monthLogsCache) {
      if (daysByKind[log.kind]) daysByKind[log.kind].add(log.log_date);
    }
    document.querySelectorAll(".log-kind-count").forEach((el) => {
      const kind = el.dataset.countFor;
      el.textContent = String(daysByKind[kind] ? daysByKind[kind].size : 0);
    });
  }

  function setActiveLogKind(kind) {
    activeLogKind = activeLogKind === kind ? null : kind;
    document.querySelectorAll(".log-kind-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.kind === activeLogKind);
    });
    renderKindLogList();
  }

  function renderKindLogList() {
    const wrap = els.successKindList;
    if (!wrap) return;
    if (!activeLogKind) {
      wrap.hidden = true;
      wrap.innerHTML = "";
      return;
    }
    wrap.hidden = false;
    wrap.innerHTML = "";

    const title = document.createElement("h3");
    title.className = "kind-log-title";
    title.textContent = `${LOG_EMOJI[activeLogKind] || ""} ${LOG_KIND_LABEL[activeLogKind] || activeLogKind}`.trim();
    wrap.appendChild(title);

    const rows = monthLogsCache.filter((l) => l.kind === activeLogKind);
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.textContent = "Пока нет записей этого типа в месяце.";
      wrap.appendChild(empty);
      return;
    }

    const ul = document.createElement("ul");
    ul.className = "day-list";
    for (const log of rows) {
      const li = document.createElement("li");
      li.className = "kind-log-item";
      const dateEl = document.createElement("div");
      dateEl.className = "kind-log-date";
      dateEl.textContent = new Date(log.log_date + "T00:00:00").toLocaleDateString("ru-RU", {
        day: "numeric", month: "long", weekday: "short",
      });
      const nameEl = document.createElement("div");
      nameEl.className = "kind-log-name";
      nameEl.textContent = log.comment || "Без названия";
      li.appendChild(dateEl);
      li.appendChild(nameEl);
      li.addEventListener("click", () => {
        openSuccessDay(log.log_date).catch((err) => showError(err.message));
      });
      ul.appendChild(li);
    }
    wrap.appendChild(ul);
  }

  async function loadSuccessMonth() {
    clearError();
    if (!successCursor) {
      const now = new Date();
      successCursor = { year: now.getFullYear(), month: now.getMonth() + 1 };
    }
    const { year, month } = successCursor;
    const data = await api(`/api/success/month?year=${year}&month=${month}`);
    monthLogsCache = data.logs || [];
    updateLogKindCounts();
    els.successLabel.textContent = data.label;
    els.successSummary.textContent =
      `База закрыта: ${data.base_closed_days} из ${data.days_in_month} · доп. упражнений: ${data.bonus_total}`;

    const first = new Date(year, month - 1, 1);
    let pad = (first.getDay() + 6) % 7;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    els.successCal.innerHTML = "";
    for (let i = 0; i < pad; i++) {
      const empty = document.createElement("div");
      empty.className = "cal-cell empty";
      els.successCal.appendChild(empty);
    }
    for (const day of data.days) {
      const cell = document.createElement("button");
      cell.type = "button";
      const d = new Date(day.date + "T00:00:00");
      cell.className = "cal-cell";
      if (day.base_done) cell.classList.add("base-done");
      if (d > today) cell.classList.add("future");
      if ((day.log_kinds || []).length) cell.classList.add("has-logs");

      const dayEl = document.createElement("span");
      dayEl.className = "cal-day";
      dayEl.textContent = String(d.getDate());
      cell.appendChild(dayEl);

      if (day.exercise_count > 0) {
        const countEl = document.createElement("span");
        countEl.className = "cal-bonus";
        countEl.textContent = String(day.exercise_count);
        cell.appendChild(countEl);
      }

      if ((day.log_kinds || []).length) {
        const marks = document.createElement("span");
        marks.className = "cal-marks";
        marks.textContent = day.log_kinds.map((k) => LOG_EMOJI[k] || "•").join("");
        cell.appendChild(marks);
      }

      cell.addEventListener("click", () => {
        openSuccessDay(day.date).catch((err) => showError(err.message));
      });
      els.successCal.appendChild(cell);
    }

    renderKindLogList();
  }

  function shiftSuccessMonth(delta) {
    if (!successCursor) return;
    let { year, month } = successCursor;
    month += delta;
    if (month < 1) {
      month = 12;
      year -= 1;
    } else if (month > 12) {
      month = 1;
      year += 1;
    }
    successCursor = { year, month };
    activeLogKind = null;
    document.querySelectorAll(".log-kind-btn").forEach((btn) => btn.classList.remove("active"));
    showSuccessMonth();
    loadSuccessMonth().catch((err) => showError(err.message));
  }

  function shiftDateStr(dateStr, deltaDays) {
    const d = new Date(dateStr + "T12:00:00");
    d.setDate(d.getDate() + deltaDays);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function todayStr() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function renderDayExerciseList(title, items, emptyText, { interactive = false, planDate = null } = {}) {
    const wrap = document.createElement("div");
    const h = document.createElement("h3");
    h.textContent = title;
    wrap.appendChild(h);
    if (!items.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = emptyText;
      wrap.appendChild(p);
      return wrap;
    }
    const ul = document.createElement("ul");
    ul.className = "day-list";
    for (const ex of items) {
      const li = document.createElement("li");
      if (ex.completed) li.classList.add("done");
      if (interactive && planDate) {
        li.classList.add("day-ex-toggle");
        li.addEventListener("click", async () => {
          try {
            await api("/api/progress", {
              method: "POST",
              body: JSON.stringify({
                catalog_exercise_id: ex.id,
                block: "base",
                completed: !ex.completed,
                plan_date: planDate,
              }),
            });
            const next = await api(`/api/success/day/${planDate}`);
            renderSuccessDay(next);
          } catch (err) {
            showError(err.message);
          }
        });
      }
      const name = document.createElement("div");
      name.textContent = (ex.completed ? "✓ " : "○ ") + (ex.name || "Упражнение");
      li.appendChild(name);
      if (ex.description && ex.description !== ex.name) {
        const d = document.createElement("div");
        d.className = "muted";
        d.textContent = ex.description;
        li.appendChild(d);
      }
      ul.appendChild(li);
    }
    wrap.appendChild(ul);
    return wrap;
  }

  function renderDayLogs(day) {
    const wrap = document.createElement("div");
    const h = document.createElement("h3");
    h.textContent = "Мои записи";
    wrap.appendChild(h);
    if (!day.logs.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "Пока нет записей — можно добавить силовую или фейсфитнес.";
      wrap.appendChild(p);
      return wrap;
    }
    const ul = document.createElement("ul");
    ul.className = "day-list";
    for (const log of day.logs) {
      const li = document.createElement("li");
      li.className = "log-item";
      const body = document.createElement("div");
      const kind = document.createElement("div");
      kind.className = "log-kind";
      kind.textContent = log.kind_label;
      const text = document.createElement("div");
      text.textContent = log.comment;
      body.appendChild(kind);
      body.appendChild(text);
      li.appendChild(body);
      const del = document.createElement("button");
      del.type = "button";
      del.className = "btn tiny ghost";
      del.textContent = "✕";
      del.addEventListener("click", async () => {
        try {
          const next = await api(`/api/success/logs/${log.id}`, { method: "DELETE" });
          renderSuccessDay(next);
        } catch (err) {
          showError(err.message);
        }
      });
      li.appendChild(del);
      ul.appendChild(li);
    }
    wrap.appendChild(ul);
    return wrap;
  }

  function renderSuccessDay(day) {
    selectedSuccessDate = day.date;
    els.successMonthWrap.hidden = true;
    els.successDayWrap.hidden = false;
    els.successDayTitle.textContent = new Date(day.date + "T00:00:00").toLocaleDateString("ru-RU", {
      weekday: "long", day: "numeric", month: "long",
    });
    const totalDone = day.base_completed + (day.bonus_exercises?.length || 0);
    els.successDayStatus.textContent = day.base_done
      ? `База закрыта · ${day.base_completed}/${day.base_total} · всего упражнений: ${totalDone}`
      : day.base_total
        ? `База: ${day.base_completed}/${day.base_total}`
        : "Плана ещё не было — можно закрыть базу или добавить запись";

    if (els.successDayComplete) {
      els.successDayComplete.hidden = !!day.base_done;
      els.successDayComplete.disabled = day.date > todayStr();
    }

    els.successDayBase.innerHTML = "";
    els.successDayBase.appendChild(
      renderDayExerciseList("База", day.base_exercises, "Нет упражнений базы — нажми «Закрыть базу»", {
        interactive: true,
        planDate: day.date,
      })
    );
    els.successDayBonus.innerHTML = "";
    els.successDayBonus.appendChild(
      renderDayExerciseList("Дополнительно", day.bonus_exercises, "Допов не было")
    );
    els.successDayLogs.innerHTML = "";
    els.successDayLogs.appendChild(renderDayLogs(day));

    els.logKind.innerHTML = (day.activity_kinds || [])
      .map((k) => `<option value="${k.id}">${k.label}</option>`)
      .join("");
  }

  async function openSuccessDay(dateStr) {
    clearError();
    const day = await api(`/api/success/day/${dateStr}`);
    renderSuccessDay(day);
  }

  function openForm(row) {
    clearError();
    editingId = row ? row.id : null;
    els.formTitle.textContent = row ? `Редактировать #${row.id}` : "Новое упражнение";
    if (categories.length && els.fCategory.options.length === 0) {
      fillCategorySelects();
    }
    const cat = row ? row.category : (categories[0]?.id || "posture");
    els.fCategory.value = cat;
    els.fName.value = row?.name || "";
    els.fDesc.value = row?.description || "";
    els.fVideo.value = row?.video_url || "";
    els.fOrder.value = String(row?.sort_order ?? 0);
    els.fActive.checked = row ? row.is_active !== false : true;

    // Show only the form (list is long — form was below the fold)
    document.getElementById("admin-list-wrap")?.classList.add("is-hidden");
    els.adminForm.hidden = false;
    els.viewAdmin.hidden = false;
    els.viewWorkout.hidden = true;
    els.adminForm.scrollIntoView({ behavior: "smooth", block: "start" });
    els.fName.focus();
  }

  function closeForm() {
    els.adminForm.hidden = true;
    document.getElementById("admin-list-wrap")?.classList.remove("is-hidden");
  }

  function exerciseCard(ex, { selectable, onSelect, onToggle, title, subtitle }) {
    const li = document.createElement("li");
    li.className = "item" + (ex.completed ? " done" : "") + (ex.selected ? " selected" : "");
    const mainTitle = title != null ? title : ex.name;
    const mainSubtitle = subtitle != null ? subtitle : ex.description;
    const showTitle = !!(mainTitle && String(mainTitle).trim());
    const showSubtitle = !!(mainSubtitle && String(mainSubtitle).trim() && mainSubtitle !== mainTitle);

    li.innerHTML = `
      <div class="check"></div>
      <div class="body grow">
        ${showTitle ? `<p class="name"></p>` : ""}
        ${showSubtitle ? `<p class="desc"></p>` : ""}
      </div>
      ${ex.video_url ? `<button type="button" class="video-btn inline">Видео</button>` : ""}
    `;
    if (showTitle) li.querySelector(".name").textContent = mainTitle;
    if (showSubtitle) li.querySelector(".desc").textContent = mainSubtitle;

    const videoBtn = li.querySelector(".video-btn");
    if (videoBtn && ex.video_url) {
      videoBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openVideo(ex.video_url);
      });
    }
    li.addEventListener("click", async () => {
      li.style.opacity = "0.6";
      try {
        if (selectable) await onSelect(ex);
        else await onToggle(ex);
        if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
      } catch (err) {
        showError(err.message);
      } finally {
        li.style.opacity = "1";
      }
    });
    return li;
  }

  function renderChecklistBlock(sec, plan, rerender, block, { hint } = {}) {
    const wrap = document.createElement("section");
    wrap.className = "section" + (sec.kind === "extra" ? " optional" : "");
    const list = document.createElement("ul");
    list.className = "list";

    const item = document.createElement("li");
    item.className = "item variants-block checklist-block";

    const body = document.createElement("div");
    body.className = "body full";

    const title = document.createElement("p");
    title.className = "name block-title";
    title.textContent = sec.title;
    body.appendChild(title);

    if (hint) {
      const h = document.createElement("p");
      h.className = "hint";
      h.textContent = hint;
      body.appendChild(h);
    }

    const opts = sec.options?.length ? sec.options : (sec.exercises || []);
    if (!opts.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.textContent = "Упражнения ещё не добавлены.";
      body.appendChild(empty);
    } else {
      const rows = document.createElement("div");
      rows.className = "variants";
      for (const opt of opts) {
        const row = document.createElement("div");
        row.className = "check-row-item" + (opt.completed ? " done" : "");

        const check = document.createElement("div");
        check.className = "check";
        row.appendChild(check);

        const textWrap = document.createElement("div");
        textWrap.className = "variant-text";
        const name = document.createElement("p");
        name.className = "variant-name";
        const { title: t, subtitle: s } = fixedDisplay({ title: sec.title }, opt);
        name.textContent = t;
        textWrap.appendChild(name);
        if (s) {
          const d = document.createElement("p");
          d.className = "variant-desc";
          d.textContent = s;
          textWrap.appendChild(d);
        }
        row.appendChild(textWrap);

        if (opt.video_url) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "video-btn inline";
          btn.textContent = "Видео";
          btn.addEventListener("click", (ev) => {
            ev.stopPropagation();
            openVideo(opt.video_url);
          });
          row.appendChild(btn);
        }

        row.addEventListener("click", async () => {
          row.style.opacity = "0.6";
          try {
            rerender(await api("/api/progress", {
              method: "POST",
              body: JSON.stringify({
                catalog_exercise_id: opt.id,
                block,
                completed: !opt.completed,
              }),
            }));
            if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
          } catch (err) {
            showError(err.message);
          } finally {
            row.style.opacity = "1";
          }
        });

        rows.appendChild(row);
      }
      body.appendChild(rows);
    }

    item.appendChild(body);
    list.appendChild(item);
    wrap.appendChild(list);
    return wrap;
  }

  function fixedDisplay(sec, ex) {
    const name = (ex?.name || "").trim();
    const desc = (ex?.description || "").trim();
    if (name && desc && name !== desc) {
      return { title: name, subtitle: desc };
    }
    if (name) {
      return { title: name, subtitle: "" };
    }
    return { title: desc || (sec.title || "").trim() || "Упражнение", subtitle: "" };
  }

  function renderSection(sec, plan, rerender) {
    const wrap = document.createElement("section");
    wrap.className = "section" + (sec.kind === "bonus" || sec.kind === "muscle" ? " optional" : "");

    const block = blockBySection[sec.key] || "base";
    const list = document.createElement("ul");
    list.className = "list";

    // Slot 1 / 2: one compact card
    if (sec.kind === "fixed") {
      const ex = sec.exercises[0];
      if (!ex) {
        const head = document.createElement("div");
        head.className = "section-head";
        head.innerHTML = `<h2></h2><p class="hint">Упражнение ещё не задано в каталоге.</p>`;
        head.querySelector("h2").textContent = sec.title;
        wrap.appendChild(head);
        return wrap;
      }
      const { title, subtitle } = fixedDisplay(sec, ex);
      list.appendChild(
        exerciseCard(ex, {
          selectable: false,
          title,
          subtitle,
          onSelect: async () => {},
          onToggle: async (item) => {
            rerender(await api("/api/progress", {
              method: "POST",
              body: JSON.stringify({
                catalog_exercise_id: item.id,
                block,
                completed: !item.completed,
              }),
            }));
          },
        })
      );
      wrap.appendChild(list);
      return wrap;
    }

    // Декольте: one field — one checkbox + variants with video links
    if (sec.kind === "variants") {
      const item = document.createElement("li");
      item.className = "item variants-block" + (sec.section_completed ? " done" : "");

      const check = document.createElement("div");
      check.className = "check";
      item.appendChild(check);

      const body = document.createElement("div");
      body.className = "body";

      const title = document.createElement("p");
      title.className = "name";
      title.textContent = sec.title;
      body.appendChild(title);

      const opts = sec.options || [];
      if (!opts.length) {
        const hint = document.createElement("p");
        hint.className = "hint";
        hint.textContent = "Варианты ещё не добавлены в каталог.";
        body.appendChild(hint);
      } else {
        const variants = document.createElement("div");
        variants.className = "variants";
        for (const opt of opts) {
          const row = document.createElement("div");
          row.className = "variant-row";
          const textWrap = document.createElement("div");
          textWrap.className = "variant-text";
          const name = document.createElement("p");
          name.className = "variant-name";
          name.textContent = opt.name || opt.description || "Вариант";
          textWrap.appendChild(name);
          if (opt.description && opt.description !== opt.name) {
            const d = document.createElement("p");
            d.className = "variant-desc";
            d.textContent = opt.description;
            textWrap.appendChild(d);
          }
          row.appendChild(textWrap);
          if (opt.video_url) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "video-btn inline";
            btn.textContent = "Видео";
            btn.addEventListener("click", (ev) => {
              ev.stopPropagation();
              openVideo(opt.video_url);
            });
            row.appendChild(btn);
          }
          variants.appendChild(row);
        }
        body.appendChild(variants);
      }

      item.appendChild(body);
      item.addEventListener("click", async () => {
        item.style.opacity = "0.6";
        try {
          rerender(await api("/api/progress", {
            method: "POST",
            body: JSON.stringify({
              section: sec.key,
              block: "base",
              completed: !sec.section_completed,
            }),
          }));
          if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
        } catch (err) {
          showError(err.message);
        } finally {
          item.style.opacity = "1";
        }
      });

      list.appendChild(item);
      wrap.appendChild(list);
      return wrap;
    }

    // Осанка / шея / попа / доп. блоки
    if (sec.kind === "checklist" || sec.kind === "extra") {
      return renderChecklistBlock(sec, plan, rerender, block);
    }

    return wrap;
  }

  function renderExtras(plan, rerender) {
    const wrap = document.createElement("div");
    wrap.className = "extras";

    const btns = document.createElement("div");
    btns.className = "extras-btns";

    const extras = plan.extras || [];
    const kindByKey = { more_posture: "posture", more_glutes: "glutes" };

    for (const extra of extras) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn extras-btn" + (expandedExtras[extra.key] ? " active" : "");
      btn.textContent = extra.title || extra.key;
      btn.disabled = !extra.can_add;
      btn.addEventListener("click", async () => {
        if (!extra.can_add) return;
        btn.disabled = true;
        try {
          expandedExtras[extra.key] = true;
          const next = await api("/api/extra", {
            method: "POST",
            body: JSON.stringify({ kind: kindByKey[extra.key] }),
          });
          rerender(next);
          if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
        } catch (err) {
          showError(err.message);
          btn.disabled = !extra.can_add;
        }
      });
      btns.appendChild(btn);
    }
    wrap.appendChild(btns);

    for (const extra of extras) {
      if (!expandedExtras[extra.key] && !(extra.options && extra.options.length)) continue;
      if (extra.options && extra.options.length) {
        expandedExtras[extra.key] = true;
        wrap.appendChild(
          renderChecklistBlock(extra, plan, rerender, blockBySection[extra.key] || "bonus")
        );
      }
    }
    return wrap;
  }

  function renderWorkout(plan) {
    clearError();
    els.empty.hidden = true;
    if (els.pageHeader) els.pageHeader.classList.remove("is-hidden");
    els.title.classList.add("date-heading");
    els.title.textContent = new Date(plan.plan_date + "T00:00:00").toLocaleDateString("ru-RU", {
      weekday: "long", day: "numeric", month: "long",
    });
    els.meta.hidden = true;
    els.meta.textContent = "";
    const pct = plan.base_total ? Math.round((plan.base_completed / plan.base_total) * 100) : 0;
    els.bar.hidden = false;
    els.fill.style.width = pct + "%";
    if (plan.base_done) {
      els.label.textContent = `База закрыта · ${plan.base_completed} из ${plan.base_total}`;
      setCongratsVisible(true, CONGRATS_TEXT);
    } else {
      els.label.textContent = `База: ${plan.base_completed} из ${plan.base_total} · ${pct}%`;
      setCongratsVisible(false);
    }
    els.sections.innerHTML = "";
    const rerender = (p) => applyPlan(p);
    for (const sec of plan.sections) {
      els.sections.appendChild(renderSection(sec, plan, rerender));
    }
    if (plan.extras && plan.extras.length) {
      els.sections.appendChild(renderExtras(plan, rerender));
    }
  }

  function fillCategorySelects() {
    const opts = categories.map((c) => `<option value="${c.id}">${c.label}</option>`).join("");
    els.adminCategory.innerHTML = `<option value="">Все категории</option>` + opts;
    els.fCategory.innerHTML = opts;
  }

  async function loadAdminList() {
    clearError();
    const cat = els.adminCategory.value;
    const q = cat ? `?category=${encodeURIComponent(cat)}` : "";
    const rows = await api("/api/catalog" + q);
    els.adminList.innerHTML = "";
    if (!rows.length) {
      els.adminList.innerHTML = `<li class="hint">Пусто в этой категории</li>`;
      return;
    }
    for (const row of rows) {
      const li = document.createElement("li");
      li.className = "admin-item" + (row.is_active ? "" : " inactive");
      const label = categories.find((c) => c.id === row.category)?.label || row.category;
      li.innerHTML = `
        <div class="admin-item-body">
          <p class="name"></p>
          <p class="desc"></p>
        </div>
        <div class="admin-item-actions">
          <button type="button" class="btn tiny edit">Изменить</button>
          <button type="button" class="btn tiny ghost toggle"></button>
          <button type="button" class="btn tiny danger del">Удалить</button>
        </div>
      `;
      li.querySelector(".name").textContent = `#${row.id} · ${label} · ${row.name}`;
      li.querySelector(".desc").textContent = row.description || (row.video_url ? "есть видео" : "без описания");
      const toggleBtn = li.querySelector(".toggle");
      toggleBtn.textContent = row.is_active ? "Выкл" : "Вкл";
      li.querySelector(".edit").addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        try {
          openForm(row);
        } catch (err) {
          showError(err.message || String(err));
        }
      });
      toggleBtn.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        try {
          await api(`/api/catalog/${row.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !row.is_active }),
          });
          await loadAdminList();
        } catch (err) {
          showError(err.message);
        }
      });
      li.querySelector(".del").addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (!confirm(`Удалить «${row.name}»?`)) return;
        try {
          await api(`/api/catalog/${row.id}`, { method: "DELETE" });
          await loadAdminList();
        } catch (err) {
          showError(err.message);
        }
      });
      els.adminList.appendChild(li);
    }
  }

  async function saveForm() {
    const payload = {
      category: els.fCategory.value,
      name: els.fName.value.trim(),
      description: els.fDesc.value.trim() || null,
      video_url: els.fVideo.value.trim() || null,
      sort_order: Number(els.fOrder.value) || 0,
      is_active: els.fActive.checked,
    };
    if (!payload.name) {
      showError("Укажи название");
      return;
    }
    try {
      if (editingId) {
        await api(`/api/catalog/${editingId}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        const { is_active, ...createPayload } = payload;
        await api("/api/catalog", { method: "POST", body: JSON.stringify(createPayload) });
        if (!is_active) {
          // created active by default; deactivate if needed
          const list = await api(`/api/catalog?category=${encodeURIComponent(payload.category)}`);
          const created = list.filter((r) => r.name === payload.name).pop();
          if (created) {
            await api(`/api/catalog/${created.id}`, {
              method: "PATCH",
              body: JSON.stringify({ is_active: false }),
            });
          }
        }
      }
      closeForm();
      await loadAdminList();
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (err) {
      showError(err.message);
    }
  }

  function wireTabs() {
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const view = btn.dataset.view;
        try {
          if (view === "workout") {
            setView("workout");
            const plan = await api("/api/plan/today");
            applyPlan(plan);
          } else if (view === "success") {
            setView("success");
          } else if (view === "admin") {
            setView("admin");
          }
        } catch (err) {
          showError(err.message);
        }
      });
    });
    els.successPrev?.addEventListener("click", () => shiftSuccessMonth(-1));
    els.successNext?.addEventListener("click", () => shiftSuccessMonth(1));
    document.querySelectorAll(".log-kind-btn").forEach((btn) => {
      btn.addEventListener("click", () => setActiveLogKind(btn.dataset.kind));
    });
    els.successDayBack?.addEventListener("click", () => {
      showSuccessMonth();
      loadSuccessMonth().catch((err) => showError(err.message));
    });
    els.successDayPrev?.addEventListener("click", () => {
      if (!selectedSuccessDate) return;
      openSuccessDay(shiftDateStr(selectedSuccessDate, -1)).catch((err) => showError(err.message));
    });
    els.successDayNext?.addEventListener("click", () => {
      if (!selectedSuccessDate) return;
      openSuccessDay(shiftDateStr(selectedSuccessDate, 1)).catch((err) => showError(err.message));
    });
    els.successDayComplete?.addEventListener("click", async () => {
      if (!selectedSuccessDate) return;
      if (!confirm("Отметить всю базу за этот день как сделанную?")) return;
      try {
        await api("/api/progress/complete-base", {
          method: "POST",
          body: JSON.stringify({ plan_date: selectedSuccessDate }),
        });
        await openSuccessDay(selectedSuccessDate);
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      } catch (err) {
        showError(err.message);
      }
    });
    els.btnCompleteBase?.addEventListener("click", async () => {
      if (!confirm("Отметить все упражнения базы как сделанные?")) return;
      try {
        const plan = await api("/api/progress/complete-base", {
          method: "POST",
          body: JSON.stringify({}),
        });
        applyPlan(plan);
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      } catch (err) {
        showError(err.message);
      }
    });
    document.querySelectorAll("[data-quick-log]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const kind = btn.dataset.quickLog;
        const labels = { strength: "силовой", face: "лице", note: "заметке" };
        const comment = window.prompt(`Комментарий к ${labels[kind] || "записи"}:`);
        if (comment == null) return;
        const text = comment.trim();
        if (!text) {
          showError("Нужен комментарий");
          return;
        }
        try {
          await api("/api/success/logs", {
            method: "POST",
            body: JSON.stringify({
              log_date: todayStr(),
              kind,
              comment: text,
            }),
          });
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          if (typeof tg?.showAlert === "function") tg.showAlert("Запись сохранена");
          else alert("Запись сохранена");
        } catch (err) {
          showError(err.message);
        }
      });
    });
    els.logForm?.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (!selectedSuccessDate) return;
      try {
        const day = await api("/api/success/logs", {
          method: "POST",
          body: JSON.stringify({
            log_date: selectedSuccessDate,
            kind: els.logKind.value,
            comment: els.logComment.value,
          }),
        });
        els.logComment.value = "";
        renderSuccessDay(day);
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      } catch (err) {
        showError(err.message);
      }
    });
  }

  function wireAdmin() {
    els.adminCategory.addEventListener("change", () => loadAdminList());
    document.getElementById("admin-new").addEventListener("click", () => openForm(null));
    document.getElementById("f-save").addEventListener("click", saveForm);
    document.getElementById("f-cancel").addEventListener("click", closeForm);
    document.getElementById("admin-reload-seed").addEventListener("click", async () => {
      if (!confirm("Заменить весь каталог из catalog_seed.json? Планы дня сбросятся.")) return;
      try {
        const res = await api("/api/catalog/reload-seed", { method: "POST" });
        alert(`Загружено упражнений: ${res.loaded}`);
        await loadAdminList();
      } catch (err) {
        showError(err.message);
      }
    });
  }

  async function boot() {
    if (!initData()) {
      els.title.textContent = "Открой из Telegram";
      els.meta.textContent = "Mini App работает внутри Telegram.";
      showError("Нет initData — запусти приложение через бота.");
      return;
    }
    try {
      const me = await api("/api/me");
      isAdmin = !!me.is_admin;
      els.tabs.hidden = false;
      wireTabs();
      if (isAdmin) {
        document.querySelectorAll(".tab.admin-only").forEach((el) => { el.hidden = false; });
        categories = await api("/api/meta/categories");
        fillCategorySelects();
        wireAdmin();
      }
      const plan = await api("/api/plan/today");
      if (!plan.base_total && plan.sections.every((s) => !s.exercises.length && !s.options.length)) {
        els.title.textContent = "Каталог пуст";
        els.empty.hidden = false;
        if (isAdmin) els.meta.textContent = "Открой вкладку «Админка» и добавь упражнения.";
        return;
      }
      currentPlan = null;
      applyPlan(plan);
    } catch (err) {
      els.title.textContent = "Не удалось загрузить";
      showError(err.message);
    }
  }

  boot();
})();
