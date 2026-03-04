(function () {
    const root = document.getElementById("employee-calendar");
    if (!root) {
        return;
    }

    const requestScript = document.getElementById("employee-request-data");
    const holidayScript = document.getElementById("employee-holiday-data");
    const selectedSeedScript = document.getElementById("employee-selected-seed");

    let currentMonth = Number(root.dataset.month);
    let currentYear = Number(root.dataset.year);
    const hasCountry = root.dataset.hasCountry === "1";
    const userId = root.dataset.userId || "anon";
    const revokeTemplate = root.dataset.revokeTemplate || "";
    const requestRevokeTemplate = root.dataset.requestRevokeTemplate || "";
    const storageKey = `calendario_selected_dates_${userId}`;

    const requestData = JSON.parse(requestScript ? requestScript.textContent : "[]");
    const holidayData = JSON.parse(holidayScript ? holidayScript.textContent : "[]");

    const requestMap = {};
    requestData.forEach((item) => {
        requestMap[item.date] = item;
    });

    const holidayMap = {};
    holidayData.forEach((item) => {
        holidayMap[item.date] = item;
    });

    const grid = document.getElementById("employee-calendar-grid");
    const selectedInput = document.getElementById("id_selected_dates");
    const clearButton = document.getElementById("clear-selection");
    const sendButton = document.getElementById("send-request");
    const selectedCountValue = document.getElementById("selected-count-value");
    const selectedDatesText = document.getElementById("selected-dates-text");
    const toggleManageModeButton = document.getElementById("toggle-manage-mode");
    const manageActions = document.getElementById("manage-actions");
    const manageSummary = document.getElementById("manage-summary");
    const bulkRequestApprovalButton = document.getElementById("bulk-request-approval");
    const bulkRevokePendingButton = document.getElementById("bulk-revoke-pending");
    const bulkRequestRevokeButton = document.getElementById("bulk-request-revoke");
    const bulkCheckedDatesRequestInput = document.getElementById("bulk-checked-dates-request");
    const bulkRequestIdsPendingInput = document.getElementById("bulk-request-ids-pending");
    const bulkRequestIdsApprovedInput = document.getElementById("bulk-request-ids-approved");
    const bulkCheckedDatesPendingInput = document.getElementById("bulk-checked-dates-pending");
    const bulkCheckedDatesApprovedInput = document.getElementById("bulk-checked-dates-approved");
    const bulkNextInputs = document.querySelectorAll(".bulk-next-input");
    const monthSelect = document.getElementById("month-select");
    const yearInput = document.getElementById("year-input");
    const prevMonthButton = document.getElementById("prev-month");
    const nextMonthButton = document.getElementById("next-month");
    const currentMonthTitle = document.getElementById("current-month-title");
    const monthHolidayCountNode = document.getElementById("month-holiday-count");
    const hiddenMonthInput = document.getElementById("selected-month-hidden");
    const hiddenYearInput = document.getElementById("selected-year-hidden");
    const navigationSelectedInput = document.getElementById("navigation-selected-dates");
    const navigationForm = monthSelect ? monthSelect.closest("form") : null;
    const requestForm = document.getElementById("day-selection-form");

    let isMouseDown = false;
    let dragMode = null;
    let suppressClick = false;
    let manageModeEnabled = false;
    const dragVisited = new Set();
    const manageCheckedDates = [];

    function loadSelectedDates() {
        try {
            const raw = window.localStorage.getItem(storageKey);
            if (!raw) {
                return [];
            }
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            const unique = [];
            parsed.forEach((item) => {
                if (typeof item === "string" && /^\d{4}-\d{2}-\d{2}$/.test(item) && !unique.includes(item)) {
                    unique.push(item);
                }
            });
            return unique;
        } catch (error) {
            return [];
        }
    }

    function loadSeedDates() {
        try {
            const parsed = JSON.parse(selectedSeedScript ? selectedSeedScript.textContent : "[]");
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed.filter((item) => typeof item === "string" && /^\d{4}-\d{2}-\d{2}$/.test(item));
        } catch (error) {
            return [];
        }
    }

    function mergeUniqueDates(left, right) {
        const merged = [];
        [...left, ...right].forEach((item) => {
            if (!merged.includes(item)) {
                merged.push(item);
            }
        });
        return merged;
    }

    const selectedDates = mergeUniqueDates(loadSeedDates(), loadSelectedDates());

    function persistSelectedDates() {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify(selectedDates));
        } catch (error) {
            // ignore storage errors
        }
    }

    function getCookie(name) {
        const cookieValue = document.cookie
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith(`${name}=`));
        return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
    }

    function getCsrfToken() {
        const fromCookie = getCookie("csrftoken");
        if (fromCookie) {
            return fromCookie;
        }
        const input = document.querySelector("input[name='csrfmiddlewaretoken']");
        return input ? input.value : "";
    }

    function buildActionUrl(template, requestId) {
        return template.replace(/\/0\//, `/${requestId}/`);
    }

    function currentPagePath() {
        return `${window.location.pathname}${window.location.search}`;
    }

    function formatDate(yearValue, monthValue, dayValue) {
        const monthPart = String(monthValue).padStart(2, "0");
        const dayPart = String(dayValue).padStart(2, "0");
        return `${yearValue}-${monthPart}-${dayPart}`;
    }

    function isWeekendParts(yearValue, monthValue, dayValue) {
        const weekday = new Date(yearValue, monthValue - 1, dayValue).getDay();
        return weekday === 0 || weekday === 6;
    }

    function isWeekendDateKey(dateKey) {
        const parts = dateKey.split("-");
        if (parts.length !== 3) {
            return false;
        }
        const yearValue = Number(parts[0]);
        const monthValue = Number(parts[1]);
        const dayValue = Number(parts[2]);
        if (!Number.isInteger(yearValue) || !Number.isInteger(monthValue) || !Number.isInteger(dayValue)) {
            return false;
        }
        return isWeekendParts(yearValue, monthValue, dayValue);
    }

    function dateBelongsToCurrentMonth(dateKey) {
        return dateKey.startsWith(`${String(currentYear)}-${String(currentMonth).padStart(2, "0")}-`);
    }

    function isLockedDate(dateKey) {
        const request = requestMap[dateKey];
        if (isWeekendDateKey(dateKey)) {
            return true;
        }
        if (holidayMap[dateKey]) {
            return true;
        }
        return Boolean(request && (request.status === "approved" || request.status === "pending"));
    }

    function canSelectInManageMode(dateKey) {
        return !isWeekendDateKey(dateKey) && !holidayMap[dateKey];
    }

    function pruneLockedSelections() {
        for (let i = selectedDates.length - 1; i >= 0; i -= 1) {
            if (isLockedDate(selectedDates[i])) {
                selectedDates.splice(i, 1);
            }
        }
    }

    function pruneManageCheckedDates() {
        for (let i = manageCheckedDates.length - 1; i >= 0; i -= 1) {
            if (!canSelectInManageMode(manageCheckedDates[i])) {
                manageCheckedDates.splice(i, 1);
            }
        }
    }

    function countHolidaysForCurrentMonth() {
        let count = 0;
        Object.keys(holidayMap).forEach((dateKey) => {
            if (dateBelongsToCurrentMonth(dateKey)) {
                count += 1;
            }
        });
        return count;
    }

    function getMonthName(monthValue) {
        if (!monthSelect) {
            return `Month ${monthValue}`;
        }
        const option = monthSelect.querySelector(`option[value="${monthValue}"]`);
        return option ? option.textContent : `Month ${monthValue}`;
    }

    function updateHeaderAndControls() {
        if (monthSelect) {
            monthSelect.value = String(currentMonth);
        }
        if (yearInput) {
            yearInput.value = String(currentYear);
        }
        if (hiddenMonthInput) {
            hiddenMonthInput.value = String(currentMonth);
        }
        if (hiddenYearInput) {
            hiddenYearInput.value = String(currentYear);
        }
        if (currentMonthTitle) {
            currentMonthTitle.textContent = `${getMonthName(currentMonth)} ${currentYear}`;
        }
        if (monthHolidayCountNode) {
            monthHolidayCountNode.textContent = hasCountry ? String(countHolidaysForCurrentMonth()) : "Assign country";
        }
    }

    function selectionText() {
        if (!selectedDates.length) {
            return "No dates selected";
        }
        const preview = selectedDates.slice(0, 8);
        const suffix = selectedDates.length > preview.length ? ` (+${selectedDates.length - preview.length} more)` : "";
        return `${preview.join(", ")}${suffix}`;
    }

    function syncManageUi() {
        pruneManageCheckedDates();

        if (manageActions) {
            manageActions.classList.toggle("hidden", !manageModeEnabled);
        }
        if (toggleManageModeButton) {
            toggleManageModeButton.textContent = manageModeEnabled ? "Exit Select Mode" : "Select Mode";
        }

        const pendingRequestIds = [];
        const approvedRequestIds = [];
        let requestApprovalEligible = 0;
        let revokePendingEligible = 0;
        let requestRevokeEligible = 0;

        manageCheckedDates.forEach((dateKey) => {
            const request = requestMap[dateKey];
            const selectableInSelectMode = canSelectInManageMode(dateKey);
            if (!selectableInSelectMode) {
                return;
            }

            if (!request || request.status === "rejected" || request.status === "cancelled") {
                requestApprovalEligible += 1;
            }

            if (request && request.status === "pending" && request.id) {
                pendingRequestIds.push(request.id);
                revokePendingEligible += 1;
            }

            if (request && request.status === "approved" && !request.revoke_requested && request.id) {
                approvedRequestIds.push(request.id);
                requestRevokeEligible += 1;
            }
        });
        const uniquePendingIds = Array.from(new Set(pendingRequestIds));
        const uniqueApprovedIds = Array.from(new Set(approvedRequestIds));

        if (bulkRequestIdsPendingInput) {
            bulkRequestIdsPendingInput.value = JSON.stringify(uniquePendingIds);
        }
        if (bulkRequestIdsApprovedInput) {
            bulkRequestIdsApprovedInput.value = JSON.stringify(uniqueApprovedIds);
        }
        if (bulkCheckedDatesRequestInput) {
            bulkCheckedDatesRequestInput.value = JSON.stringify(manageCheckedDates);
        }
        if (bulkCheckedDatesPendingInput) {
            bulkCheckedDatesPendingInput.value = JSON.stringify(manageCheckedDates);
        }
        if (bulkCheckedDatesApprovedInput) {
            bulkCheckedDatesApprovedInput.value = JSON.stringify(manageCheckedDates);
        }
        bulkNextInputs.forEach((input) => {
            input.value = currentPagePath();
        });
        if (bulkRequestApprovalButton) {
            bulkRequestApprovalButton.disabled = requestApprovalEligible === 0;
        }
        if (bulkRevokePendingButton) {
            bulkRevokePendingButton.disabled = revokePendingEligible === 0;
        }
        if (bulkRequestRevokeButton) {
            bulkRequestRevokeButton.disabled = requestRevokeEligible === 0;
        }

        if (manageSummary) {
            if (!manageModeEnabled) {
                manageSummary.textContent = "Select mode off";
            } else {
                manageSummary.textContent = (
                    `${manageCheckedDates.length} day(s) checked | `
                    + `request: ${requestApprovalEligible}, `
                    + `revoke pending: ${revokePendingEligible}, `
                    + `revoke approved: ${requestRevokeEligible}`
                );
            }
        }
    }

    function createPendingPopover(dateKey, request) {
        const popover = document.createElement("div");
        popover.className = "employee-pending-popover";

        const title = document.createElement("div");
        title.className = "employee-popover-title";
        title.textContent = `${dateKey} - Pending`;
        popover.appendChild(title);

        if (request.note) {
            const note = document.createElement("div");
            note.className = "employee-popover-note";
            note.textContent = request.note;
            popover.appendChild(note);
        }

        const form = document.createElement("form");
        form.method = "post";
        form.action = buildActionUrl(revokeTemplate, request.id);
        form.className = "employee-revoke-form";

        const csrf = document.createElement("input");
        csrf.type = "hidden";
        csrf.name = "csrfmiddlewaretoken";
        csrf.value = getCsrfToken();
        form.appendChild(csrf);

        const nextInput = document.createElement("input");
        nextInput.type = "hidden";
        nextInput.name = "next";
        nextInput.value = currentPagePath();
        form.appendChild(nextInput);

        const button = document.createElement("button");
        button.type = "submit";
        button.className = "reject-btn tiny-btn";
        button.textContent = "Revoke";
        form.appendChild(button);

        popover.appendChild(form);
        return popover;
    }

    function createApprovedPopover(dateKey, request) {
        const popover = document.createElement("div");
        popover.className = "employee-pending-popover";

        const title = document.createElement("div");
        title.className = "employee-popover-title";
        title.textContent = `${dateKey} - Approved`;
        popover.appendChild(title);

        if (request.revoke_requested) {
            const info = document.createElement("div");
            info.className = "employee-popover-note";
            info.textContent = "Revoke request already sent to admin.";
            popover.appendChild(info);
            return popover;
        }

        const form = document.createElement("form");
        form.method = "post";
        form.action = buildActionUrl(requestRevokeTemplate, request.id);
        form.className = "employee-revoke-form";

        const csrf = document.createElement("input");
        csrf.type = "hidden";
        csrf.name = "csrfmiddlewaretoken";
        csrf.value = getCsrfToken();
        form.appendChild(csrf);

        const nextInput = document.createElement("input");
        nextInput.type = "hidden";
        nextInput.name = "next";
        nextInput.value = currentPagePath();
        form.appendChild(nextInput);

        const button = document.createElement("button");
        button.type = "submit";
        button.className = "approve-btn tiny-btn";
        button.textContent = "Request Revoke";
        form.appendChild(button);

        popover.appendChild(form);
        return popover;
    }

    function syncSelectionUi() {
        pruneLockedSelections();

        const allDateCells = grid.querySelectorAll(".calendar-cell[data-date]");
        allDateCells.forEach((cell) => {
            cell.classList.remove("state-selected");
            const badge = cell.querySelector(".selection-order");
            if (badge) {
                badge.remove();
            }
        });

        selectedDates.forEach((dateKey, index) => {
            if (!dateBelongsToCurrentMonth(dateKey)) {
                return;
            }
            const cell = grid.querySelector(`.calendar-cell[data-date="${dateKey}"]`);
            if (!cell) {
                return;
            }
            cell.classList.add("state-selected");
            const badge = document.createElement("span");
            badge.className = "selection-order";
            badge.textContent = String(index + 1);
            cell.appendChild(badge);
        });

        selectedInput.value = JSON.stringify(selectedDates);
        if (navigationSelectedInput) {
            navigationSelectedInput.value = selectedDates.length ? JSON.stringify(selectedDates) : "";
        }
        persistSelectedDates();

        const hasSelection = selectedDates.length > 0;
        if (sendButton) {
            sendButton.disabled = !hasSelection;
        }
        if (clearButton) {
            clearButton.disabled = !hasSelection;
        }
        if (selectedCountValue) {
            selectedCountValue.textContent = String(selectedDates.length);
        }
        if (selectedDatesText) {
            selectedDatesText.textContent = selectionText();
        }
        syncManageUi();
    }

    function setSelected(dateKey, shouldSelect) {
        const index = selectedDates.indexOf(dateKey);
        if (shouldSelect && index === -1) {
            selectedDates.push(dateKey);
        }
        if (!shouldSelect && index !== -1) {
            selectedDates.splice(index, 1);
        }
        syncSelectionUi();
    }

    function navigateTo(monthValue, yearValue) {
        const params = new URLSearchParams(window.location.search);
        params.set("month", String(monthValue));
        params.set("year", String(yearValue));
        if (selectedDates.length) {
            params.set("selected_dates", JSON.stringify(selectedDates));
        } else {
            params.delete("selected_dates");
        }
        window.location.search = params.toString();
    }

    function draw() {
        grid.innerHTML = "";

        const firstOfMonth = new Date(currentYear, currentMonth - 1, 1);
        const dayCount = new Date(currentYear, currentMonth, 0).getDate();
        const mondayOffset = (firstOfMonth.getDay() + 6) % 7;

        for (let i = 0; i < mondayOffset; i += 1) {
            const placeholder = document.createElement("div");
            placeholder.className = "calendar-cell empty";
            grid.appendChild(placeholder);
        }

        for (let day = 1; day <= dayCount; day += 1) {
            const dateKey = formatDate(currentYear, currentMonth, day);
            const request = requestMap[dateKey];
            const holiday = holidayMap[dateKey];
            const isWeekend = isWeekendParts(currentYear, currentMonth, day);
            const wrapper = document.createElement("div");
            wrapper.className = "employee-day-wrap";
            let pendingPopover = null;

            const cell = document.createElement("button");
            cell.type = "button";
            cell.className = "calendar-cell active-day";
            cell.dataset.date = dateKey;

            const dayNode = document.createElement("span");
            dayNode.className = "cell-day";
            dayNode.textContent = String(day);
            cell.appendChild(dayNode);

            if (isWeekend) {
                cell.classList.add("state-weekend");
                const note = document.createElement("span");
                note.className = "cell-note";
                note.textContent = "Weekend";
                cell.appendChild(note);
                cell.dataset.locked = "1";
                cell.disabled = true;
                cell.classList.remove("active-day");
                cell.title = "Weekend (not selectable)";
            }

            if (holiday) {
                cell.classList.add("state-holiday");
                const note = document.createElement("span");
                note.className = "cell-note";
                note.textContent = holiday.name;
                cell.appendChild(note);
                cell.dataset.locked = "1";
                cell.disabled = true;
                cell.classList.remove("active-day");
                cell.title = `${holiday.name} (public holiday, not selectable)`;
            }

            if (request) {
                cell.classList.add(`state-${request.status}`);
                const note = document.createElement("span");
                note.className = "cell-note";
                note.textContent = request.status.charAt(0).toUpperCase() + request.status.slice(1);
                cell.appendChild(note);

                if (request.status === "approved" || request.status === "pending") {
                    cell.dataset.locked = "1";
                    cell.classList.remove("active-day");
                }

                if (request.status === "approved") {
                    cell.disabled = true;
                }

                if (request.status === "pending" && request.id) {
                    wrapper.classList.add("pending-revokable");
                    const hint = document.createElement("span");
                    hint.className = "hover-hint pending-hint";
                    hint.textContent = "Hover to revoke";
                    cell.appendChild(hint);
                    pendingPopover = createPendingPopover(dateKey, request);
                }

                if (request.status === "approved" && request.id) {
                    wrapper.classList.add("pending-revokable");
                    const hint = document.createElement("span");
                    hint.className = "hover-hint pending-hint";
                    hint.textContent = request.revoke_requested ? "Revoke requested" : "Hover to request revoke";
                    cell.appendChild(hint);
                    pendingPopover = createApprovedPopover(dateKey, request);
                }
            }

            cell.addEventListener("mousedown", (event) => {
                if (manageModeEnabled || cell.disabled || cell.dataset.locked === "1") {
                    return;
                }
                event.preventDefault();
                isMouseDown = true;
                dragVisited.clear();
                const shouldSelect = !selectedDates.includes(dateKey);
                dragMode = shouldSelect ? "add" : "remove";
                dragVisited.add(dateKey);
                setSelected(dateKey, shouldSelect);
                suppressClick = true;
            });

            cell.addEventListener("mouseenter", () => {
                if (manageModeEnabled || !isMouseDown || !dragMode || cell.disabled || cell.dataset.locked === "1") {
                    return;
                }
                if (dragVisited.has(dateKey)) {
                    return;
                }
                dragVisited.add(dateKey);
                setSelected(dateKey, dragMode === "add");
            });

            cell.addEventListener("click", (event) => {
                if (suppressClick) {
                    suppressClick = false;
                    event.preventDefault();
                    return;
                }
                if (manageModeEnabled || cell.disabled || cell.dataset.locked === "1") {
                    return;
                }
                setSelected(dateKey, !selectedDates.includes(dateKey));
            });

            const manageCheckbox = document.createElement("input");
            manageCheckbox.type = "checkbox";
            manageCheckbox.className = "manage-day-checkbox";
            manageCheckbox.dataset.date = dateKey;
            if (request && request.id) {
                manageCheckbox.dataset.requestId = String(request.id);
            }
            const selectableInSelectMode = !isWeekend && !holiday;
            if (!selectableInSelectMode) {
                const selectedIndex = manageCheckedDates.indexOf(dateKey);
                if (selectedIndex >= 0) {
                    manageCheckedDates.splice(selectedIndex, 1);
                }
                manageCheckbox.disabled = true;
                manageCheckbox.classList.add("locked-checkbox");
            }
            manageCheckbox.checked = selectableInSelectMode && manageCheckedDates.includes(dateKey);
            wrapper.classList.toggle("manage-checked", manageCheckbox.checked);

            manageCheckbox.addEventListener("click", (event) => {
                event.stopPropagation();
            });
            manageCheckbox.addEventListener("change", () => {
                const currentIndex = manageCheckedDates.indexOf(dateKey);
                if (manageCheckbox.checked && currentIndex === -1) {
                    manageCheckedDates.push(dateKey);
                }
                if (!manageCheckbox.checked && currentIndex >= 0) {
                    manageCheckedDates.splice(currentIndex, 1);
                }
                wrapper.classList.toggle("manage-checked", manageCheckbox.checked);
                syncManageUi();
            });

            wrapper.appendChild(cell);
            if (pendingPopover) {
                wrapper.appendChild(pendingPopover);
            }
            wrapper.appendChild(manageCheckbox);
            grid.appendChild(wrapper);
        }

        updateHeaderAndControls();
        syncSelectionUi();
    }

    document.addEventListener("mouseup", () => {
        isMouseDown = false;
        dragMode = null;
        dragVisited.clear();
    });

    if (prevMonthButton) {
        prevMonthButton.addEventListener("click", () => {
            let monthValue = currentMonth - 1;
            let yearValue = currentYear;
            if (monthValue < 1) {
                monthValue = 12;
                yearValue -= 1;
            }
            navigateTo(monthValue, yearValue);
        });
    }

    if (nextMonthButton) {
        nextMonthButton.addEventListener("click", () => {
            let monthValue = currentMonth + 1;
            let yearValue = currentYear;
            if (monthValue > 12) {
                monthValue = 1;
                yearValue += 1;
            }
            navigateTo(monthValue, yearValue);
        });
    }

    if (navigationForm) {
        navigationForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const monthValue = Number(monthSelect.value);
            const yearValue = Number(yearInput.value);
            if (!Number.isInteger(monthValue) || monthValue < 1 || monthValue > 12) {
                return;
            }
            if (!Number.isInteger(yearValue) || yearValue < 1900 || yearValue > 2300) {
                return;
            }
            navigateTo(monthValue, yearValue);
        });
    }

    if (requestForm) {
        requestForm.addEventListener("submit", (event) => {
            pruneLockedSelections();
            if (!selectedDates.length) {
                event.preventDefault();
                syncSelectionUi();
                return;
            }
            selectedInput.value = JSON.stringify(selectedDates);
            if (hiddenMonthInput) {
                hiddenMonthInput.value = String(currentMonth);
            }
            if (hiddenYearInput) {
                hiddenYearInput.value = String(currentYear);
            }
        });
    }

    if (monthSelect) {
        monthSelect.addEventListener("change", () => {
            const chosen = Number(monthSelect.value);
            if (chosen >= 1 && chosen <= 12) {
                currentMonth = chosen;
                updateHeaderAndControls();
            }
        });
    }

    if (yearInput) {
        yearInput.addEventListener("input", () => {
            const maybeYear = Number(yearInput.value);
            if (Number.isInteger(maybeYear) && maybeYear >= 1900 && maybeYear <= 2300) {
                currentYear = maybeYear;
                updateHeaderAndControls();
            }
        });
    }

    if (toggleManageModeButton) {
        toggleManageModeButton.addEventListener("click", () => {
            const enteringSelectMode = !manageModeEnabled;
            manageModeEnabled = enteringSelectMode;

            if (enteringSelectMode && selectedDates.length) {
                selectedDates.forEach((dateKey) => {
                    if (canSelectInManageMode(dateKey) && !manageCheckedDates.includes(dateKey)) {
                        manageCheckedDates.push(dateKey);
                    }
                });
                root.classList.toggle("select-mode", manageModeEnabled);
                syncManageUi();
                return;
            }

            const syncedFromSelectMode = mergeUniqueDates(
                [],
                manageCheckedDates.filter((dateKey) => canSelectInManageMode(dateKey))
            );
            selectedDates.splice(0, selectedDates.length, ...syncedFromSelectMode);
            root.classList.toggle("select-mode", manageModeEnabled);
            syncSelectionUi();
        });
    }

    draw();
})();
