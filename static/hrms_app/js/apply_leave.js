/**
 * LeaveManager
 * Refactored class-based implementation for Leave Management logic.
 * Maintains original jQuery dependencies and DOM structure.
 */
class LeaveManager {
    constructor() {
        // State Management
        this.baseTotalDays = 0; // Stores the count from date generation before half-day adjustments

        // Globals assumed to exist per instructions: leaveBalance, leaveTypeShortCode

        this.init();
    }

    /**
     * Initialize listeners and initial state
     */
    init() {
        // Destroy existing select2 instances to prevent conflicts
        $('select').select2('destroy');

        // Bind DOM events
        this.bindEvents();

        // Initial Calculation
        this.handleDateChange();
    }

    /**
     * Bind all event listeners
     */
    bindEvents() {
        // Date Picker Change Event
        $(document).on('dp.change', () => {
            // Note: URL param logic commented out in original, kept consistent here
            this.handleDateChange();
        });

        // Leave Option (Half-day/Full-day) Change Event
        $(document).on('change', '.leaveOption', (e) => this.handleOptionChange(e));
    }

    /**
     * formatting helper: Date to YYYY-MM-DD
     */
    formatDateToYMD(date) {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    /**
     * Async API wrapper for fetching holidays
     * Replaces $.ajax({ async: false })
     */
    async fetchHolidays(startDate, endDate) {
        return new Promise((resolve, reject) => {
            $.ajax({
                url: `/api/v1/holidays/?start_date=${this.formatDateToYMD(startDate)}&end_date=${this.formatDateToYMD(endDate)}`,
                type: "GET",
                success: (response) => {
                    const holidayMap = {};
                    if (response.results && response.results.data) {
                        response.results.data.forEach(holiday => {
                            holidayMap[holiday.start_date] = holiday.title;
                        });
                    }
                    resolve(holidayMap);
                },
                error: (xhr, status, error) => {
                    console.error("Error fetching holidays", error);
                    resolve({}); // Resolve empty on error to prevent crash
                }
            });
        });
    }

    /**
     * Main handler for Date Input changes
     * Orchestrates the flow: Validates -> Fetches Data -> Renders -> Updates Balance
     */
    async handleDateChange() {
        const startDate = $('#id_startDate').val();
        const endDate = $('#id_endDate').val();

        if (startDate && endDate) {
            // Adjust min-date logic for end date
            const startDateObj = new Date(startDate);
            startDateObj.setDate(startDateObj.getDate() - 1);
            const minDate = startDateObj.toISOString().split('T')[0];
            $('#id_endDate').attr('data-min-date', minDate);

            // Calculate days (now async)
            this.baseTotalDays = await this.calculateTotalDays(startDate, endDate);

            // Update Booked Balance UI
            this.calculateBookedBalance(this.baseTotalDays, startDate);
            // $('#balances').show();
        }
    }

    /**
     * Handler for Half-day/Full-day dropdown changes
     * Syncs start/end dropdowns and triggers recalculation
     */
    handleOptionChange(e) {
        const $this = $(e.currentTarget);

        // Use setTimeout(0) to allow UI thread to settle (preserved from original)
        setTimeout(() => {
            const selectId = $this.attr('id');
            const selectedValue = $this.val();
            const startDate = $('#id_startDate').val();
            const endDate = $('#id_endDate').val();

            let startDay = $('#id_startDayChoice').val();
            let endDay = $('#id_endDayChoice').val();

            // Sync Logic: Start Day
            if (selectId && selectId.startsWith('id_startDayChoice')) {
                startDay = selectedValue;
                $('#id_startDayChoice').val(selectedValue);

                if (startDate === endDate) {
                    endDay = selectedValue;
                    $('#id_endDayChoice').val(selectedValue);
                }
            }
            // Sync Logic: End Day
            else if (selectId && selectId.startsWith('id_endDayChoice')) {
                endDay = selectedValue;
                $('#id_endDayChoice').val(selectedValue);

                if (startDate === endDate) {
                    startDay = selectedValue;
                    $('#id_startDayChoice').val(selectedValue);
                }
            }

            // Recalculate with new dropdown values
            this.updateTotalDays(startDay, endDay);
        }, 0);
    }

    /**
     * Logic to calculate final days based on Half-Day/Full-Day selection
     * Applies adjustments to this.baseTotalDays
     */
    updateTotalDays(startDay, endDay) {
        const startDate = $('#id_startDate').val();
        const endDate = $('#id_endDate').val();

        if (startDate > endDate) {
            alert("Start date cannot be after end date.");
            return;
        }

        const adjustments = {
            "1-1": 0,    // Full - Full
            "2-2": -0.5, // 1st Half - 1st Half
            "3-2": -1,   // 2nd Half - 1st Half
            "3-1": -0.5, // 2nd Half - Full
            "1-2": -0.5, // Full - 1st Half
        };

        let adjustment = 0;

        if (startDate === endDate) {
            // Same day logic
            if (startDay === "1" && this.baseTotalDays >= "1") {
                adjustment = 0;
            } else if ((this.baseTotalDays - 0.5) < 0) {
                alert("Insufficient leave balance for this request.");
                return;
            } else {
                adjustment = -0.5;
            }
        } else {
            const key = `${startDay}-${endDay}`;
            adjustment = adjustments[key] || 0;
        }

        const newTotalDays = this.baseTotalDays + adjustment;

        if (newTotalDays < 0) {
            alert("Insufficient leave balance for this request.");
            return;
        }

        $('#totalDays').text(newTotalDays);
        this.setBalance(leaveBalance, newTotalDays);
    }

    /**
     * Wrapper for generating options
     */
    async calculateTotalDays(startDate, endDate) {
        return await this.generateDateOptions(startDate, endDate);
    }

    /**
     * Core Logic: Generates HTML Table, Fetches Holidays, Calculates Base Days
     */
    async generateDateOptions(startDate, endDate) {
        const currentDate = new Date(startDate);
        const endDateObj = new Date(endDate);
        let tableHTML = '<table class="table">';
        let calculatedDays = 0;

        // Async Holiday Fetch
        const holidays = await this.fetchHolidays(startDate, endDate);

        // Edge Case: Same Day + Sunday/Holiday -> Critical Alert & Reload
        if (startDate === endDate) {
            const checkDate = new Date(startDate);
            const isSunday = checkDate.getDay() === 0;
            const formattedForHoliday = checkDate.toLocaleDateString('en-CA');
            const isHoliday = holidays.hasOwnProperty(formattedForHoliday);

            if (isSunday || isHoliday) {
                alert("Selected date is either a Sunday or a Holiday. Leave cannot be applied.");
                $('#dateOptions').html("");
                $('#totalDays').text("0 Day(s)");

                setTimeout(() => location.reload(), 100);
                return 0;
            }
        }

        // Loop through date range
        while (currentDate <= endDateObj) {
            const formattedDateStr = currentDate.toDateString();
            const isStart = formattedDateStr === new Date(startDate).toDateString();
            const isEnd = formattedDateStr === new Date(endDate).toDateString();
            const isSunday = currentDate.getDay() === 0;

            // Format for Holiday Lookup (en-CA is yyyy-mm-dd)
            const lookupDate = currentDate.toLocaleDateString('en-CA');
            const holidayTitle = holidays[lookupDate] || "";

            // CL Rule: Exclude Sundays & Holidays
            if (leaveTypeShortCode === 'CL' && (isSunday || holidayTitle)) {
                calculatedDays--;
            }

            // HTML Rendering Logic
            let colorClass = "text-dark";
            let displayText = formattedDateStr;

            if (leaveTypeShortCode === 'CL' && isSunday) {
                displayText += ' - Weekly Off';
                colorClass = "text-danger";
            }

            tableHTML += '<tr>';
            tableHTML += `<td class="formattedDate ${colorClass} font-weight-bold">${displayText} ${holidayTitle ? ` - ${holidayTitle}` : ''}</td>`;
            tableHTML += '<td>';

            // Dropdown Rendering
            if (isStart) {
                tableHTML += `<select id="id_startDayChoice" class="form-select leaveOption id_startDayChoice">
                                <option value="1">Full Day</option>
                                <option value="2">First Half</option>
                                <option value="3">Second Half</option>
                              </select>`;
                calculatedDays++;
            } else if (isEnd) {
                tableHTML += `<select id="id_endDayChoice" class="form-select leaveOption id_endDayChoice">
                                <option value="1">Full Day</option>
                                <option value="2">First Half</option>
                              </select>`;
                calculatedDays++;
            } else {
                tableHTML += `<select class="form-select leaveOption">
                                <option value="1">Full Day</option>
                              </select>`;
                calculatedDays++;
            }

            tableHTML += '</td></tr>';

            // Increment Date
            currentDate.setDate(currentDate.getDate() + 1);
        }

        tableHTML += '</table>';
        $('#dateOptions').html(tableHTML);
        $('#totalDays').text(calculatedDays + ' Day(s)');

        return calculatedDays;
    }

    /**
     * Updates the "As of [Date]" text and sets initial balance
     */
    calculateBookedBalance(totalDays, startDate) {
        const dateObject = new Date(startDate);
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        const day = dateObject.getDate();
        const monthIndex = dateObject.getMonth();
        const year = dateObject.getFullYear();
        const formattedDate = `${day}-${monthNames[monthIndex]}-${year}`;

        $('#td_date').text('As of ' + formattedDate);
        this.setBalance(leaveBalance, totalDays);
    }

    /**
     * Updates Input Fields and Validates Submit Button based on Balance
     */
    setBalance(typeBal, totalDays) {
        $('#currentlyBooked').text(totalDays);
        $('#remainingBal').text(typeBal - totalDays);
        $('#id_usedLeave').val(totalDays);
        $('#id_balanceLeave').val(typeBal - totalDays);

        if (leaveTypeShortCode !== 'LWP') {
            const currentBalance = $('#id_balanceLeave').val();
            if (currentBalance < 0) {
                $('#applyLeaveButton').prop('disabled', true);
            } else {
                $('#applyLeaveButton').prop('disabled', false);
            }
        }
    }
}

// Initialize on Document Ready
$(document).ready(function () {
    new LeaveManager();
});