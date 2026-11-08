function openModal(modalId, eventId) {
const modal = document.getElementById(modalId);
modal.style.display = 'flex';
modal.querySelector('input[name="event_id"]').value = eventId;
modal.querySelector('input[name="action_type"]').value = "add_wagon";
}

function closeModal(id) {
document.getElementById(id).style.display = 'none';
}

function openAddEvent() {
const modal = document.getElementById("addEvent");
modal.style.display = 'flex'
modal.querySelector('input[name="action_type"]').value = "add_event";
}

function openAddDestination() {
const modal = document.getElementById("addDestination");
modal.style.display = "flex"
modal.querySelector('input[name="action_type"]').value = "add_destination";
}

function openAddTariff() {
const modal = document.getElementById("addTariff");
modal.style.display = "flex"
modal.querySelector('input[name="action_type"]').value = "add_tariff";
}

function openEditEvent(eventId) {
const modal = document.getElementById("editEvent");
modal.style.display = "flex";
modal.querySelector('input[name="event_id"]').value = eventId;
modal.querySelector('input[name="action_type"]').value = "edit_event";
}

function openEditWagon(wagonId) {
const modal = document.getElementById("editWagon");
modal.style.display = "flex";
modal.querySelector('input[name="wagon_id"]').value = wagonId;
modal.querySelector('input[name="action_type"]').value = "edit_wagon";
}

function exportExcelByConfig() {
const modal = document.getElementById("exportExcelDate");
modal.style.display = "flex";
}


window.addEventListener("beforeunload", function () {
        localStorage.setItem("scrollPosition", window.scrollY);
    });

    window.addEventListener("load", function () {
        let scrollPos = localStorage.getItem("scrollPosition");
        if (scrollPos) {
            window.scrollTo(0, parseInt(scrollPos));
            localStorage.removeItem("scrollPosition"); // Если надо сбросить после восстановления
        }
    });