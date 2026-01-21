/**
 * ShortLeaveManager
 * Handles the UI logic, calculations, and API interactions for the Short Leave Application.
 */
class ShortLeaveManager {
    constructor() {
        this.cacheDOM();
        this.bindEvents();
        this.init();
    }

    cacheDOM() {
        // Form & Inputs
        this.$form = $('#short-leave-form');
        this.$startDate = $('#id_startDate');
        this.$fromTime = $('#id_from_time');
        this.$toTime = $('#id_to_time');
        this.$submitBtn = $('#btnTriggerModal');
        this.$finalSubmitBtn = $('#btnFinalSubmit');
        
        // Summary Elements
        this.$summaryDate = $('#summaryDate');
        this.$summaryTime = $('#summaryTime');
        this.$summaryDuration = $('#summaryDuration');
        this.$attendanceWindow = $('#attendanceWindow');
        this.$attendanceMissing = $('#attendanceMissing');
        this.$eligibilityMsg = $('#eligibilityMessage');
        this.$loader = $('#apiLoader');

        // Modal Elements
        this.$modalDate = $('#modalConfirmDate');
        this.$modalDuration = $('#modalConfirmDuration');

        // Config
        this.apiUrl = '/api/v1/attendance/summary/';
    }

    bindEvents() {
        // Use document delegation if elements are dynamic, otherwise direct bind
        // Assuming 'dp.change' is the event from your specific DatePicker library
        $(document).on('dp.change', '#id_startDate', () => this.handleDateChange());
        
        // Listen to time inputs
        this.$fromTime.on('change', () => this.handleTimeInput());
        this.$toTime.on('change', () => this.handleTimeInput());
        
        // Final Submit
        this.$finalSubmitBtn.on('click', () => this.submitForm());
    }

    init() {
        // Initial check in case of page reload with data
        if(this.$startDate.val()) {
            this.handleDateChange();
        }
    }

    // ============================
    // Logic Handlers
    // ============================

    async handleDateChange() {
        const dateVal = this.$startDate.val();
        if (!dateVal) return;

        // Update UI immediate feedback
        this.$summaryDate.text(dateVal);
        this.$modalDate.text(dateVal);

        // Reset previous attendance data
        this.resetAttendanceData();

        // Fetch new data
        await this.fetchAttendanceSummary(this.formatDateToYMD(dateVal));
    }

    handleTimeInput() {
        const from = this.$fromTime.val();
        const to = this.$toTime.val();

        if (!from || !to) {
            this.updateDurationDisplay(null);
            return;
        }

        // Update Summary Time Range
        this.$summaryTime.text(`${from} - ${to}`);

        // Calculate Duration
        const fromMin = this.timeToMinutes(from);
        const toMin = this.timeToMinutes(to);

        if (toMin <= fromMin) {
            // Invalid range
            this.updateDurationDisplay(null);
            // Optionally add field error class here
            return;
        }

        const duration = toMin - fromMin;
        this.updateDurationDisplay(duration);
    }

    submitForm() {
        // Disable button to prevent double submit
        this.$finalSubmitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Sending...');
        this.$form.submit();
    }

    // ============================
    // API & Data
    // ============================

    async fetchAttendanceSummary(dateFormatted) {
        this.toggleLoader(true);
        
        try {
            // Construct URL with query params
            const url = `${this.apiUrl}?date=${dateFormatted}&leave_type=STL`;
            
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) throw new Error("Network response was not ok");

            const data = await response.json();
            this.renderAttendanceData(data);

        } catch (error) {
            console.error("Attendance Fetch Error:", error);
            this.$attendanceWindow.html('<span class="text-danger">Error fetching data</span>');
        } finally {
            this.toggleLoader(false);
        }
    }

    renderAttendanceData(data) {
        // 1. Attendance Window
        if (data.attendance_start && data.attendance_end) {
            const start = this.formatTime(data.attendance_start);
            const end = this.formatTime(data.attendance_end);
            this.$attendanceWindow.text(`${start} - ${end}`);
        } else {
            this.$attendanceWindow.text('No punch data');
        }

        // 2. Missing Hours (System calculated)
        const missingHHMM = this.minutesToHHMM(data.missing_minutes);
        this.$attendanceMissing.text(missingHHMM);

        // 3. Eligibility Gate (Enable/Disable Submit)
        const isEligible = data.eligible && data.attendance_complete;
        this.$submitBtn.prop('disabled', !isEligible);
        
        if (!isEligible) {
            this.$eligibilityMsg.text("You are not eligible for short leave on this date (Attendance incomplete or missing).");
            this.$eligibilityMsg.addClass("text-danger");
        } else {
            this.$eligibilityMsg.text("");
        }
    }

    // ============================
    // Helpers & Formatting
    // ============================

    resetAttendanceData() {
        this.$attendanceWindow.text('--');
        this.$attendanceMissing.text('--:--');
        this.$submitBtn.prop('disabled', true);
        this.$eligibilityMsg.text("");
    }

    toggleLoader(show) {
        if (show) {
            this.$loader.removeClass('d-none');
        } else {
            this.$loader.addClass('d-none');
        }
    }

    updateDurationDisplay(minutes) {
        if (minutes === null) {
            this.$summaryDuration.text('--:--');
            this.$modalDuration.text('--:--');
            return;
        }
        const formatted = this.minutesToHHMM(minutes);
        this.$summaryDuration.text(formatted);
        this.$modalDuration.text(formatted);
    }

    formatDateToYMD(dateString) {
        // Depending on your input format, you might need parsing. 
        // Assuming input is readable by Date() or already YYYY-MM-DD
        const d = new Date(dateString);
        if (isNaN(d.getTime())) return dateString; // Return as is if parse fails (fallback)
        
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    timeToMinutes(timeStr) {
        const [h, m] = timeStr.split(':').map(Number);
        return (h * 60) + m;
    }

    minutesToHHMM(minutes) {
        if (minutes == null || isNaN(minutes)) return '--:--';
        const m = Math.abs(minutes); // handle negative just in case
        const hrs = Math.floor(m / 60);
        const mins = m % 60;
        return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
    }

    formatTime(dateTimeStr) {
        return new Date(dateTimeStr).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }
}

// Initialize on Document Ready
$(document).ready(function () {
    window.shortLeaveManager = new ShortLeaveManager();
});