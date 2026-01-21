(function () {
    function toggleFields() {
        const leaveUnit = document.getElementById("id_leave_unit")?.value;
        const accrual = document.getElementById("id_accrual_period")?.value;

        const halfDayFields = [
            "id_allow_half_day",
            "id_half_day_value",
            "id_half_day_short_code",
        ];

        const durationFields = [
            "id_min_duration",
            "id_max_duration",
        ];

        function setVisibility(fieldIds, show) {
            fieldIds.forEach((id) => {
                const row = document.getElementById(id)?.closest(".form-row");
                if (row) row.style.display = show ? "block" : "none";
            });
        }

        // Day-based logic
        if (leaveUnit === "DAY") {
            setVisibility(halfDayFields, true);
            setVisibility(durationFields, false);
        } else {
            setVisibility(halfDayFields, false);
            setVisibility(durationFields, true);
        }

        // Monthly accrual warning
        if (accrual === "MONTHLY") {
            document.body.classList.add("monthly-leave");
        } else {
            document.body.classList.remove("monthly-leave");
        }
    }

    document.addEventListener("DOMContentLoaded", toggleFields);
    document.addEventListener("change", toggleFields);
})();
