(function () {
    const root = document.getElementById("manager-calendar");
    if (!root) {
        return;
    }

    const employeeEventsScript = document.getElementById("manager-employee-events");
    const holidayEventsScript = document.getElementById("manager-holiday-events");

    let currentMonth = Number(root.dataset.month);
    let currentYear = Number(root.dataset.year);
    const canSelectMode = root.dataset.canSelectMode === "1";
    const selectedEmployeeId = Number(root.dataset.selectedEmployeeId || "0");
    const approveTemplate = root.dataset.approveTemplate || "";
    const rejectTemplate = root.dataset.rejectTemplate || "";
    const revokeApprovedTemplate = root.dataset.revokeApprovedTemplate || "";
    const approveRevokeTemplate = root.dataset.approveRevokeTemplate || "";
    const rejectRevokeTemplate = root.dataset.rejectRevokeTemplate || "";

    const requestEvents = JSON.parse(employeeEventsScript ? employeeEventsScript.textContent : "[]");
    const holidayEvents = JSON.parse(holidayEventsScript ? holidayEventsScript.textContent : "[]");

    const requestMap = {};
    requestEvents.forEach((event) => {
        if (!requestMap[event.date]) {
            requestMap[event.date] = [];
        }
        requestMap[event.date].push(event);
    });

    const holidayMap = {};
    holidayEvents.forEach((event) => {
        if (!holidayMap[event.date]) {
            holidayMap[event.date] = [];
        }
        holidayMap[event.date].push({
            country: event.country || "",
            name: event.name || "",
        });
    });

    const grid = document.getElementById("manager-calendar-grid");
    const filterForm = document.getElementById("admin-filter-form");
    const monthSelect = document.getElementById("admin-month-select");
    const yearInput = document.getElementById("admin-year-input");
    const prevMonthButton = document.getElementById("admin-prev-month");
    const nextMonthButton = document.getElementById("admin-next-month");
    const monthTitle = document.getElementById("admin-current-month-title");

    const toggleSelectModeButton = document.getElementById("admin-toggle-select-mode");
    const selectSummary = document.getElementById("admin-select-summary");
    const selectActions = document.getElementById("admin-manage-actions");
    const bulkNextInputs = document.querySelectorAll(".admin-bulk-next-input");
    const bulkApproveButton = document.getElementById("admin-bulk-approve");
    const bulkRejectButton = document.getElementById("admin-bulk-reject");
    const bulkApproveRevokeButton = document.getElementById("admin-bulk-approve-revoke");
    const bulkRevokeApprovedButton = document.getElementById("admin-bulk-revoke-approved");
    const bulkRejectRevokeButton = document.getElementById("admin-bulk-reject-revoke");
    const bulkApproveIdsInput = document.getElementById("admin-bulk-request-ids-approve");
    const bulkRejectIdsInput = document.getElementById("admin-bulk-request-ids-reject");
    const bulkApproveRevokeIdsInput = document.getElementById("admin-bulk-request-ids-approve-revoke");
    const bulkRevokeApprovedIdsInput = document.getElementById("admin-bulk-request-ids-revoke-approved");
    const bulkRejectRevokeIdsInput = document.getElementById("admin-bulk-request-ids-reject-revoke");
    const bulkApproveDatesInput = document.getElementById("admin-bulk-checked-dates-approve");
    const bulkRejectDatesInput = document.getElementById("admin-bulk-checked-dates-reject");
    const bulkApproveRevokeDatesInput = document.getElementById("admin-bulk-checked-dates-approve-revoke");
    const bulkRevokeApprovedDatesInput = document.getElementById("admin-bulk-checked-dates-revoke-approved");
    const bulkRejectRevokeDatesInput = document.getElementById("admin-bulk-checked-dates-reject-revoke");

    let selectModeEnabled = false;
    const checkedDates = [];

    function currentPagePath() {
        return `${window.location.pathname}${window.location.search}`;
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

    function appendNote(cell, text) {
        const note = document.createElement("span");
        note.className = "cell-note";
        note.textContent = text;
        cell.appendChild(note);
    }

    function createStatusChip(status) {
        const chip = document.createElement("span");
        chip.className = `status-chip status-${status}`;
        chip.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        return chip;
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
        if (monthTitle) {
            monthTitle.textContent = `${getMonthName(currentMonth)} ${currentYear}`;
        }
    }

    function formatDate(dayValue) {
        const monthPart = String(currentMonth).padStart(2, "0");
        const dayPart = String(dayValue).padStart(2, "0");
        return `${currentYear}-${monthPart}-${dayPart}`;
    }

    function isWeekend(dayValue) {
        const weekday = new Date(currentYear, currentMonth - 1, dayValue).getDay();
        return weekday === 0 || weekday === 6;
    }

    function isDateSelectableInSelectMode(dayIsWeekend, holidaysForDay) {
        return !dayIsWeekend && (!holidaysForDay || holidaysForDay.length === 0);
    }

    function countStatuses(requestsForDay) {
        const counts = { pending: 0, approved: 0, rejected: 0 };
        requestsForDay.forEach((item) => {
            if (counts[item.status] !== undefined) {
                counts[item.status] += 1;
            }
        });
        return counts;
    }

    function formatHolidayCompact(holidaysForDay) {
        if (!holidaysForDay || !holidaysForDay.length) {
            return "";
        }
        const countryCodes = Array.from(
            new Set(
                holidaysForDay
                    .map((item) => item.country)
                    .filter((item) => Boolean(item))
            )
        ).sort();
        if (!countryCodes.length) {
            return "Holiday";
        }
        return `Holiday ${countryCodes.map((code) => `(${code})`).join("/")}`;
    }

    function createQuickActionForm(actionUrl, buttonClass, buttonText, csrfToken, addNoteInput) {
        const form = document.createElement("form");
        form.method = "post";
        form.action = actionUrl;
        form.className = "quick-action-form";

        const csrf = document.createElement("input");
        csrf.type = "hidden";
        csrf.name = "csrfmiddlewaretoken";
        csrf.value = csrfToken;
        form.appendChild(csrf);

        const nextInput = document.createElement("input");
        nextInput.type = "hidden";
        nextInput.name = "next";
        nextInput.value = currentPagePath();
        form.appendChild(nextInput);

        if (addNoteInput) {
            const noteInput = document.createElement("input");
            noteInput.type = "text";
            noteInput.name = "note";
            noteInput.placeholder = "Optional note";
            noteInput.className = "quick-note-input";
            form.appendChild(noteInput);
        }

        const button = document.createElement("button");
        button.type = "submit";
        button.className = `${buttonClass} tiny-btn`;
        button.textContent = buttonText;
        form.appendChild(button);

        return form;
    }

    function createRequestRow(requestEvent, csrfToken) {
        const row = document.createElement("div");
        row.className = "day-request-row";

        const head = document.createElement("div");
        head.className = "day-request-head";

        const employee = document.createElement("span");
        employee.className = "day-request-employee";
        employee.textContent = requestEvent.employee;
        head.appendChild(employee);

        head.appendChild(createStatusChip(requestEvent.status));
        row.appendChild(head);

        const meta = document.createElement("div");
        meta.className = "day-request-meta";
        meta.textContent = requestEvent.country ? `Country: ${requestEvent.country}` : "Country: -";
        row.appendChild(meta);

        if (requestEvent.note) {
            const note = document.createElement("div");
            note.className = "day-request-note";
            note.textContent = `Note: ${requestEvent.note}`;
            row.appendChild(note);
        }

        if (requestEvent.status === "pending") {
            const actionWrap = document.createElement("div");
            actionWrap.className = "day-request-actions";
            actionWrap.appendChild(
                createQuickActionForm(
                    buildActionUrl(approveTemplate, requestEvent.id),
                    "approve-btn",
                    "Approve",
                    csrfToken,
                    false
                )
            );
            actionWrap.appendChild(
                createQuickActionForm(
                    buildActionUrl(rejectTemplate, requestEvent.id),
                    "reject-btn",
                    "Reject",
                    csrfToken,
                    true
                )
            );
            row.appendChild(actionWrap);
        }

        if (requestEvent.status === "approved") {
            const actionWrap = document.createElement("div");
            actionWrap.className = "day-request-actions";

            if (requestEvent.revoke_requested) {
                const revokeFlag = document.createElement("div");
                revokeFlag.className = "day-request-note";
                revokeFlag.textContent = "Revoke requested by employee.";
                row.appendChild(revokeFlag);
                actionWrap.appendChild(
                    createQuickActionForm(
                        buildActionUrl(approveRevokeTemplate, requestEvent.id),
                        "approve-btn",
                        "Approve Revoke",
                        csrfToken,
                        false
                    )
                );
                actionWrap.appendChild(
                    createQuickActionForm(
                        buildActionUrl(rejectRevokeTemplate, requestEvent.id),
                        "reject-btn",
                        "Keep Approved",
                        csrfToken,
                        true
                    )
                );
            }

            actionWrap.appendChild(
                createQuickActionForm(
                    buildActionUrl(revokeApprovedTemplate, requestEvent.id),
                    "reject-btn",
                    "Revoke Approved",
                    csrfToken,
                    false
                )
            );
            row.appendChild(actionWrap);
        }

        return row;
    }

    function createPopover(dateKey, requestsForDay, holidaysForDay, rowIndex, csrfToken) {
        const popover = document.createElement("div");
        popover.className = "admin-day-popover";
        if (rowIndex >= 4) {
            popover.classList.add("popover-up");
        }

        const title = document.createElement("div");
        title.className = "popover-title";
        title.textContent = dateKey;
        popover.appendChild(title);

        if (holidaysForDay && holidaysForDay.length) {
            const holidayBlock = document.createElement("div");
            holidayBlock.className = "popover-holidays";
            holidaysForDay.forEach((holiday) => {
                const line = document.createElement("div");
                line.className = "holiday-line";
                if (holiday.country) {
                    line.textContent = `${holiday.name} (${holiday.country})`;
                } else {
                    line.textContent = holiday.name;
                }
                holidayBlock.appendChild(line);
            });
            popover.appendChild(holidayBlock);
        }

        if (!requestsForDay.length) {
            const empty = document.createElement("div");
            empty.className = "popover-empty";
            empty.textContent = "No requests for this day.";
            popover.appendChild(empty);
            return popover;
        }

        requestsForDay
            .slice()
            .sort((a, b) => {
                const priority = { pending: 0, approved: 1, rejected: 2 };
                const left = (priority[a.status] || 9) + (a.revoke_requested ? -0.5 : 0);
                const right = (priority[b.status] || 9) + (b.revoke_requested ? -0.5 : 0);
                return left - right;
            })
            .forEach((requestEvent) => {
                popover.appendChild(createRequestRow(requestEvent, csrfToken));
            });

        return popover;
    }

    function getMatchingRequestIds(dateKey, predicate) {
        const rows = requestMap[dateKey] || [];
        return rows
            .filter((row) => {
                if (canSelectMode && selectedEmployeeId && Number(row.user_id || 0) !== selectedEmployeeId) {
                    return false;
                }
                return predicate(row);
            })
            .map((row) => row.id)
            .filter((idValue) => Number.isInteger(idValue));
    }

    function pruneCheckedDates() {
        for (let i = checkedDates.length - 1; i >= 0; i -= 1) {
            const dateKey = checkedDates[i];
            const holidaysForDay = holidayMap[dateKey] || [];
            const parts = dateKey.split("-");
            if (parts.length !== 3) {
                checkedDates.splice(i, 1);
                continue;
            }
            const dayValue = Number(parts[2]);
            if (!Number.isInteger(dayValue)) {
                checkedDates.splice(i, 1);
                continue;
            }
            if (!isDateSelectableInSelectMode(isWeekend(dayValue), holidaysForDay)) {
                checkedDates.splice(i, 1);
            }
        }
    }

    function syncSelectUi() {
        pruneCheckedDates();

        if (selectActions) {
            selectActions.classList.toggle("hidden", !selectModeEnabled || !canSelectMode);
        }
        if (toggleSelectModeButton) {
            toggleSelectModeButton.textContent = selectModeEnabled ? "Exit Select Mode" : "Select Mode";
        }

        const approvePendingIds = [];
        const rejectPendingIds = [];
        const approveRevokeIds = [];
        const revokeApprovedIds = [];
        const rejectRevokeIds = [];

        checkedDates.forEach((dateKey) => {
            approvePendingIds.push(
                ...getMatchingRequestIds(dateKey, (row) => row.status === "pending")
            );
            rejectPendingIds.push(
                ...getMatchingRequestIds(dateKey, (row) => row.status === "pending")
            );
            approveRevokeIds.push(
                ...getMatchingRequestIds(dateKey, (row) => row.status === "approved" && row.revoke_requested)
            );
            revokeApprovedIds.push(
                ...getMatchingRequestIds(dateKey, (row) => row.status === "approved")
            );
            rejectRevokeIds.push(
                ...getMatchingRequestIds(dateKey, (row) => row.status === "approved" && row.revoke_requested)
            );
        });

        const uniqueApprovePendingIds = Array.from(new Set(approvePendingIds));
        const uniqueRejectPendingIds = Array.from(new Set(rejectPendingIds));
        const uniqueApproveRevokeIds = Array.from(new Set(approveRevokeIds));
        const uniqueRevokeApprovedIds = Array.from(new Set(revokeApprovedIds));
        const uniqueRejectRevokeIds = Array.from(new Set(rejectRevokeIds));
        const checkedPayload = JSON.stringify(checkedDates);

        if (bulkApproveIdsInput) {
            bulkApproveIdsInput.value = JSON.stringify(uniqueApprovePendingIds);
        }
        if (bulkRejectIdsInput) {
            bulkRejectIdsInput.value = JSON.stringify(uniqueRejectPendingIds);
        }
        if (bulkApproveRevokeIdsInput) {
            bulkApproveRevokeIdsInput.value = JSON.stringify(uniqueApproveRevokeIds);
        }
        if (bulkRevokeApprovedIdsInput) {
            bulkRevokeApprovedIdsInput.value = JSON.stringify(uniqueRevokeApprovedIds);
        }
        if (bulkRejectRevokeIdsInput) {
            bulkRejectRevokeIdsInput.value = JSON.stringify(uniqueRejectRevokeIds);
        }
        if (bulkApproveDatesInput) {
            bulkApproveDatesInput.value = checkedPayload;
        }
        if (bulkRejectDatesInput) {
            bulkRejectDatesInput.value = checkedPayload;
        }
        if (bulkApproveRevokeDatesInput) {
            bulkApproveRevokeDatesInput.value = checkedPayload;
        }
        if (bulkRevokeApprovedDatesInput) {
            bulkRevokeApprovedDatesInput.value = checkedPayload;
        }
        if (bulkRejectRevokeDatesInput) {
            bulkRejectRevokeDatesInput.value = checkedPayload;
        }
        bulkNextInputs.forEach((input) => {
            input.value = currentPagePath();
        });

        if (bulkApproveButton) {
            bulkApproveButton.disabled = uniqueApprovePendingIds.length === 0;
        }
        if (bulkRejectButton) {
            bulkRejectButton.disabled = uniqueRejectPendingIds.length === 0;
        }
        if (bulkApproveRevokeButton) {
            bulkApproveRevokeButton.disabled = uniqueApproveRevokeIds.length === 0;
        }
        if (bulkRevokeApprovedButton) {
            bulkRevokeApprovedButton.disabled = uniqueRevokeApprovedIds.length === 0;
        }
        if (bulkRejectRevokeButton) {
            bulkRejectRevokeButton.disabled = uniqueRejectRevokeIds.length === 0;
        }

        if (selectSummary) {
            if (!canSelectMode) {
                selectSummary.textContent = "Select mode requires a single employee filter";
            } else if (!selectModeEnabled) {
                selectSummary.textContent = "Select mode off";
            } else {
                selectSummary.textContent = (
                    `${checkedDates.length} day(s) checked | `
                    + `approve: ${uniqueApprovePendingIds.length}, `
                    + `reject: ${uniqueRejectPendingIds.length}, `
                    + `approve revoke: ${uniqueApproveRevokeIds.length}, `
                    + `revoke approved: ${uniqueRevokeApprovedIds.length}, `
                    + `keep approved: ${uniqueRejectRevokeIds.length}`
                );
            }
        }
    }

    function navigateTo(monthValue, yearValue) {
        const params = new URLSearchParams(window.location.search);
        params.set("month", String(monthValue));
        params.set("year", String(yearValue));
        window.location.search = params.toString();
    }

    function draw() {
        grid.innerHTML = "";

        const firstOfMonth = new Date(currentYear, currentMonth - 1, 1);
        const dayCount = new Date(currentYear, currentMonth, 0).getDate();
        const mondayOffset = (firstOfMonth.getDay() + 6) % 7;
        const csrfToken = getCsrfToken();

        for (let i = 0; i < mondayOffset; i += 1) {
            const placeholder = document.createElement("div");
            placeholder.className = "calendar-cell empty";
            grid.appendChild(placeholder);
        }

        for (let day = 1; day <= dayCount; day += 1) {
            const dateKey = formatDate(day);
            const requestsForDay = requestMap[dateKey] || [];
            const holidaysForDay = holidayMap[dateKey] || [];
            const weekend = isWeekend(day);
            const statusCounts = countStatuses(requestsForDay);

            const wrapper = document.createElement("div");
            wrapper.className = "employee-day-wrap";

            const cell = document.createElement("div");
            cell.className = "calendar-cell manager-day-cell";
            cell.dataset.date = dateKey;

            const absoluteIndex = mondayOffset + (day - 1);
            const rowIndex = Math.floor(absoluteIndex / 7);

            const dayNode = document.createElement("span");
            dayNode.className = "cell-day";
            dayNode.textContent = String(day);
            cell.appendChild(dayNode);

            if (weekend) {
                cell.classList.add("state-weekend");
                appendNote(cell, "Weekend");
            }

            if (holidaysForDay.length) {
                cell.classList.add("state-holiday");
                appendNote(cell, formatHolidayCompact(holidaysForDay));
            }
            if (statusCounts.approved > 0) {
                cell.classList.add("state-approved");
                appendNote(cell, `Approved: ${statusCounts.approved}`);
            }
            if (statusCounts.pending > 0) {
                cell.classList.add("state-pending");
                appendNote(cell, `Pending: ${statusCounts.pending}`);
            }
            if (statusCounts.rejected > 0) {
                cell.classList.add("state-rejected");
                appendNote(cell, `Rejected: ${statusCounts.rejected}`);
            }

            if (requestsForDay.length || holidaysForDay.length || weekend) {
                const hint = document.createElement("span");
                hint.className = "hover-hint";
                hint.textContent = "Hover for details";
                cell.appendChild(hint);

                cell.appendChild(
                    createPopover(dateKey, requestsForDay, holidaysForDay, rowIndex, csrfToken)
                );
            }

            wrapper.appendChild(cell);

            if (canSelectMode) {
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.className = "manage-day-checkbox";
                checkbox.dataset.date = dateKey;

                const selectable = isDateSelectableInSelectMode(weekend, holidaysForDay);
                if (!selectable) {
                    checkbox.disabled = true;
                    checkbox.classList.add("locked-checkbox");
                }

                checkbox.checked = selectable && checkedDates.includes(dateKey);
                wrapper.classList.toggle("manage-checked", checkbox.checked);

                checkbox.addEventListener("change", () => {
                    const currentIndex = checkedDates.indexOf(dateKey);
                    if (checkbox.checked && currentIndex === -1) {
                        checkedDates.push(dateKey);
                    }
                    if (!checkbox.checked && currentIndex >= 0) {
                        checkedDates.splice(currentIndex, 1);
                    }
                    wrapper.classList.toggle("manage-checked", checkbox.checked);
                    syncSelectUi();
                });

                wrapper.appendChild(checkbox);
            }

            grid.appendChild(wrapper);
        }

        updateHeaderAndControls();
        syncSelectUi();
    }

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

    if (monthSelect) {
        monthSelect.addEventListener("change", () => {
            const monthValue = Number(monthSelect.value);
            if (monthValue >= 1 && monthValue <= 12) {
                currentMonth = monthValue;
                updateHeaderAndControls();
            }
        });
    }

    if (yearInput) {
        yearInput.addEventListener("input", () => {
            const yearValue = Number(yearInput.value);
            if (Number.isInteger(yearValue) && yearValue >= 1900 && yearValue <= 2300) {
                currentYear = yearValue;
                updateHeaderAndControls();
            }
        });
    }

    if (filterForm) {
        filterForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const monthValue = Number(monthSelect ? monthSelect.value : currentMonth);
            const yearValue = Number(yearInput ? yearInput.value : currentYear);
            if (!Number.isInteger(monthValue) || monthValue < 1 || monthValue > 12) {
                return;
            }
            if (!Number.isInteger(yearValue) || yearValue < 1900 || yearValue > 2300) {
                return;
            }
            currentMonth = monthValue;
            currentYear = yearValue;
            filterForm.submit();
        });
    }

    if (toggleSelectModeButton && canSelectMode) {
        toggleSelectModeButton.addEventListener("click", () => {
            selectModeEnabled = !selectModeEnabled;
            root.classList.toggle("select-mode", selectModeEnabled);
            syncSelectUi();
        });
    }

    draw();
})();
