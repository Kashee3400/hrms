$(document).ready(function () {
    // Hide elements initially
    $('#balances,#leave_type_div,#choices').hide();
    // Function to update date-related calculations
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

    // Bind the change event to both startDate and endDate
    $('#id_startDate, #id_endDate').change(function () {
        updateDateHandling();  // Call the update function when date is changed
    });

    // Call the same function on page load to handle initial state
    updateDateHandling();

    // Handle leave option changes
    $(document).on('change', '.leaveOption', function () {
        var selectId = $(this).attr('id');
        var selectedValue = $(this).val();
        var startDate = $('#id_startDate').val();
        var endDate = $('#id_endDate').val();
        if (selectId && selectId.startsWith('id_startDayChoice')) {
            startDay = selectedValue;
            if (startDate === endDate) {
                $('#id_endDayChoice').val(selectedValue);
                endDay = selectedValue;
            }
            $('#id_startDayChoice').val(selectedValue);
            updateTotalDays(startDay, endDay);
        } else if (selectId && selectId.startsWith('id_endDayChoice')) {
            endDay = selectedValue;
            if (startDate === endDate) {
                $('#id_startDayChoice').val(selectedValue);
                startDay = selectedValue;
            }
            $('#id_endDayChoice').val(selectedValue);
            updateTotalDays(startDay, endDay);
        }
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
        let adjustment = 0; // Default adjustment
        if (startDate === endDate) {
            // Handle same-day logic
            if (startDay === 1 && totalDays >= 1) {
                adjustment = 0;
            } else if ((totalDays - 0.5) < 0) {
                alert("Insufficient leave balance for this request.");
                return; // Exit the function if validation fails
            } else {
                adjustment = -0.5;
            }
        } else {
            // Use the lookup table to determine the adjustment
            const key = `${startDay}-${endDay}`;
            adjustment = adjustments[key] || 0; // Default to 0 if key not found
        }
        // Validate totalDays after adjustment
        const newTotalDays = totalDays + adjustment;
        if (newTotalDays < 0) {
            alert("Insufficient leave balance for this request.");
            return; // Exit the function if validation fails
        }
        // Update totalDays and balance
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
    function formatDate(dateStr) {
        var parts = dateStr.split('/');
        var dateObj = new Date(parts[2], parts[0] - 1, parts[1]);
        var formattedDate = dateObj.toLocaleDateString('en-CA');
        return formattedDate;
    }
    

    function generateDateOptions(startDate, endDate) {
        var currentDate = new Date(startDate);
        var endDateObj = new Date(endDate);
        var tableHTML = '<table class="table">';
        var totalDays = 0;
        // Fetch holiday data from API
        var formattedStartDate = formatDate(startDate);
        var formattedEndDate = formatDate(endDate);
        var holidays = {};
        $.ajax({
            url: `/api/v1/holidays/?start_date=${formattedStartDate}&end_date=${formattedEndDate}`,
            type: "GET",
            async: false,
            success: function (response) {
                console.log("API Response:", response);
                if (response.results && response.results.data) {
                    response.results.data.forEach(holiday => {
                        holidays[holiday.start_date] = holiday.title;  // Store holiday title by date
                    });
                } else {
                    console.error("Invalid response structure");
                }
            },
            error: function (xhr, status, error) {
                console.error("AJAX Error:", status, error);
                console.error("Response Text:", xhr.responseText);
            }
        });

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

            tableHTML += '<tr>';
            tableHTML += `<td class="formattedDate text-dark font-weight-bold">${formattedDate} ${holidayTitle ? ` - ${holidayTitle}` : ''}</td>`;
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


// function generateDateOptions(startDate, endDate) {
//     var currentDate = new Date(startDate);
//     var endDateObj = new Date(endDate);
//     var tableHTML = '<table class="table">';
//     var totalDays = 0;
//     while (currentDate <= endDateObj) {
//         var formattedDate = currentDate.toDateString();
//         var isStart = currentDate.toDateString() === new Date(startDate).toDateString();
//         var isEnd = currentDate.toDateString() === new Date(endDate).toDateString();

//         tableHTML += '<tr>';
//         tableHTML += '<td class="formattedDate text-dark font-weight-bold">' + formattedDate + '</td>';
//         tableHTML += '<td>';

//         if (isStart) {
//             tableHTML += '<select id="id_startDayChoice" class="form-select leaveOption id_startDayChoice">';
//             tableHTML += '<option value="1">Full Day</option>';
//             tableHTML += '<option value="2">First Half</option>';
//             tableHTML += '<option value="3">Second Half</option>';
//             tableHTML += '</select>';
//             totalDays++;
//         } else if (isEnd) {
//             tableHTML += '<select id="id_endDayChoice" class="form-select leaveOption id_endDayChoice">';
//             tableHTML += '<option value="1">Full Day</option>';
//             tableHTML += '<option value="2">First Half</option>';
//             tableHTML += '</select>';
//             totalDays++;
//         } else {
//             tableHTML += '<select class="form-select leaveOption">';
//             tableHTML += '<option value="1">Full Day</option>';
//             tableHTML += '</select>';
//             totalDays++;
//         }

//         tableHTML += '</td>';
//         tableHTML += '</tr>';
//         // Move to the next date
//         currentDate.setDate(currentDate.getDate() + 1);
//     }

//     tableHTML += '</table>';
//     $('#dateOptions').html(tableHTML)
//     $('#totalDays').text(totalDays + ' Day(s)')
//     return totalDays;
// }

