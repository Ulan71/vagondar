// VagonDar — поведение интерфейса

// Модальные окна: перед открытием сбрасываем форму и заполняем её из data-fill кнопки
document.addEventListener("show.bs.modal", (e) => {
  const modal = e.target;
  const trigger = e.relatedTarget;
  const form = modal.querySelector("form");
  if (!form || !trigger) return;

  if (form.method.toLowerCase() === "post") form.reset();

  const title = modal.querySelector(".modal-title");
  if (title) {
    title.dataset.default ??= title.textContent;
    title.textContent = trigger.dataset.title || title.dataset.default;
  }

  if (trigger.dataset.fill) {
    const data = JSON.parse(trigger.dataset.fill);
    for (const [name, value] of Object.entries(data)) {
      const field = form.elements.namedItem(name);
      if (field) field.value = value ?? "";
    }
  }
});

// Фокус на первое поле после открытия
document.addEventListener("shown.bs.modal", (e) => {
  const field = e.target.querySelector(".modal-body input:not([type=hidden]), .modal-body select, .modal-body textarea");
  if (field) field.focus();
});

// Уведомления
document.querySelectorAll(".toast").forEach((el) => bootstrap.Toast.getOrCreateInstance(el).show());

// Возврат к той же позиции прокрутки после сохранения/удаления
const scrollKey = "scroll:" + location.pathname + location.search;
window.addEventListener("beforeunload", () => {
  try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch (_) {}
});
window.addEventListener("load", () => {
  try {
    const pos = sessionStorage.getItem(scrollKey);
    if (pos) {
      window.scrollTo(0, parseInt(pos, 10));
      sessionStorage.removeItem(scrollKey);
    }
  } catch (_) {}
});
