$(document).ready(function () {
    $('select').select2('destroy');
    $(document).on('dp.change', function () {
        updateDateHandling();
    })
    updateDateHandling();
    function updateDateHandling() {
        var startDate = $('#id_startDate').val();
        var endDate = $('#id_endDate').val();
        if (startDate && endDate) {
            // Adjust the end date logic as per the original functionality
            var startDateObj = new Date(startDate);
            startDateObj.setDate(startDateObj.getDate() - 1);
            var minDate = startDateObj.toISOString().split('T')[0];
            $('#id_endDate').attr('data-min-date', minDate);
            totalDays = calculateTotalDays(startDate, endDate);
            calculateBookedBalance(totalDays, startDate);
            $('#balances').show();
        }
    }
    $(document).on('change', '.leaveOption', function () {
        const $this = $(this);
        setTimeout(function () {
            const selectId = $this.attr('id');
            const selectedValue = $this.val();
            const startDate = $('#id_startDate').val();
            const endDate = $('#id_endDate').val();
            let startDay = $('#id_startDayChoice').val();
            let endDay = $('#id_endDayChoice').val();
            if (selectId && selectId.startsWith('id_startDayChoice')) {
                startDay = selectedValue;
                $('#id_startDayChoice').val(selectedValue);

                if (startDate === endDate) {
                    endDay = selectedValue;
                    $('#id_endDayChoice').val(selectedValue);
                }
            }
            else if (selectId && selectId.startsWith('id_endDayChoice')) {
                endDay = selectedValue;
                $('#id_endDayChoice').val(selectedValue);

                if (startDate === endDate) {
                    startDay = selectedValue;
                    $('#id_startDayChoice').val(selectedValue);
                }
            }
            // Call your function to update total days
            updateTotalDays(startDay, endDay);
        }, 0);
    });

    function updateTotalDays(startDay, endDay) {
        var startDate = $('#id_startDate').val();
        var endDate = $('#id_endDate').val();
        if (startDate > endDate) {
            alert("Start date cannot be after end date.");
            return; // Exit the function if validation fails
        }
        const adjustments = {
            // Key format: "startDay-endDay"
            "1-1": 0,       // Full Day - Full Day
            "2-2": -0.5,    // First Half - First Half
            "3-2": -1,      // Second Half - First Half
            "3-1": -0.5,    // Second Half - Full Day
            "1-2": -0.5,    // Full Day - First Half
        };
        let adjustment = 0;

        if (startDate === endDate) {
            // Handle same-day logic
            if (startDay === "1" && totalDays >= "1") {
                adjustment = 0;
            } else if ((totalDays - 0.5) < 0) {
                alert("Insufficient leave balance for this request.");
                return; // Exit the function if validation fails
            } else {
                adjustment = -0.5;
            }
        } else {
            const key = `${startDay}-${endDay}`;
            adjustment = adjustments[key] || 0; // Default to 0 if key not found
        }
        const newTotalDays = totalDays + adjustment;
        if (newTotalDays < 0) {
            alert("Insufficient leave balance for this request.");
            return; // Exit the function if validation fails
        }
        $('#totalDays').text(newTotalDays);
        setBalance(leaveBalance, newTotalDays);
    }

    function calculateTotalDays(startDate, endDate) {
        return generateDateOptions(startDate, endDate);
    }

    function calculateBookedBalance(totalDays, startDate) {
        var dateObject = new Date(startDate);
        // Create an array of month names
        var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        // Get day, month, and year from the date object
        var day = dateObject.getDate();
        var monthIndex = dateObject.getMonth();
        var year = dateObject.getFullYear();
        var formattedDate = day + '-' + monthNames[monthIndex] + '-' + year;
        $('#td_date').text('As of ' + formattedDate);
        setBalance(leaveBalance, totalDays);
    }

    function setBalance(typeBal, totalDays) {
        $('#currentlyBooked').text(totalDays);
        $('#remainingBal').text(typeBal - totalDays);
        $('#id_usedLeave').val(totalDays);
        $('#id_balanceLeave').val(typeBal - totalDays);
        if (leaveTypeShortCode !== 'LWP') {
            if ($('#id_balanceLeave').val() < 0) {
                $('#applyLeaveButton').prop('disabled', true);
            }
            else {
                $('#applyLeaveButton').prop('disabled', false)
            }
        }
    }

    function generateDateOptions(startDate, endDate) {
        var currentDate = new Date(startDate);
        var endDateObj = new Date(endDate);
        var tableHTML = '<table class="table">';
        var totalDays = 0;
        var holidays = {};
        $.ajax({
            url: `/api/v1/holidays/?start_date=${startDate}&end_date=${endDate}`,
            type: "GET",
            async: false,
            success: function (response) {
                if (response.results && response.results.data) {
                    response.results.data.forEach(holiday => {
                        holidays[holiday.start_date] = holiday.title;
                    });
                } else {
                }
            },
            error: function (xhr, status, error) {
            }
        });
        // If startDate === endDate and it's a holiday or Sunday, show alert and return
        if (startDate === endDate) {
            const checkDate = new Date(startDate);
            const isSunday = checkDate.getDay() === 0;
            const formattedForHoliday = checkDate.toLocaleDateString('en-CA'); // yyyy-mm-dd
            const isHoliday = holidays.hasOwnProperty(formattedForHoliday);

            if (isSunday || isHoliday) {
                alert("Selected date is either a Sunday or a Holiday. Leave cannot be applied.");
                $('#dateOptions').html(""); // Clear table if any
                $('#totalDays').text("0 Day(s)");

                // Reload the page after a small delay
                setTimeout(() => location.reload(), 100);
                return 0;
            }
        }

        while (currentDate <= endDateObj) {
            var formattedDate = currentDate.toDateString();
            var isStart = currentDate.toDateString() === new Date(startDate).toDateString();
            var isEnd = currentDate.toDateString() === new Date(endDate).toDateString();
            var isSunday = currentDate.getDay() === 0; // Sunday check
            var holidayTitle = holidays[currentDate.toLocaleDateString('en-CA')] || "";
            // Exclude Sundays & Holidays when leaveTypeShortCode is 'CL'
            if (leaveTypeShortCode === 'CL' && (isSunday || holidayTitle)) {
                totalDays--;
            }
            var colorClass = "text-dark"
            let displayText = formattedDate;
            if (leaveTypeShortCode === 'CL' && isSunday) {
                displayText += ' - Weekly Off';
                colorClass = "text-danger";
            }
            tableHTML += '<tr>';
            tableHTML += `<td class="formattedDate  ${colorClass} font-weight-bold">${displayText} ${holidayTitle ? ` - ${holidayTitle}` : ''}</td>`;
            tableHTML += '<td>';

            if (isStart) {
                tableHTML += '<select id="id_startDayChoice" class="form-select leaveOption id_startDayChoice">';
                tableHTML += '<option value="1">Full Day</option>';
                tableHTML += '<option value="2">First Half</option>';
                tableHTML += '<option value="3">Second Half</option>';
                tableHTML += '</select>';
                totalDays++;
            } else if (isEnd) {
                tableHTML += '<select id="id_endDayChoice" class="form-select leaveOption id_endDayChoice">';
                tableHTML += '<option value="1">Full Day</option>';
                tableHTML += '<option value="2">First Half</option>';
                tableHTML += '</select>';
                totalDays++;
            } else {
                tableHTML += '<select class="form-select leaveOption">';
                tableHTML += '<option value="1">Full Day</option>';
                tableHTML += '</select>';
                totalDays++;
            }

            tableHTML += '</td>';
            tableHTML += '</tr>';
            // Move to the next date
            currentDate.setDate(currentDate.getDate() + 1);
        }

        tableHTML += '</table>';
        $('#dateOptions').html(tableHTML)
        $('#totalDays').text(totalDays + ' Day(s)')
        return totalDays;
    }

});
